"""V13: private, optional fine-tuning of a *real* local multilingual Sentence Transformer.

Research-only passage retrieval. No remote model loading, applicant decisions,
label inference, or model promotion. Annotations are explicitly human supplied.

Operational data controls:
- model checkpoint is loaded from an explicitly local path, with remote code disabled
- tenant and authorized-document scope precede passage embedding
- families are held out; all labeled evaluation docs are embargoed from training
- train + calibration determine checkpoint; test labels are read only for final evaluation
- reports have aggregate numbers, hashes and training configuration, never CV text
- trained weights are sensitive and MUST stay in private encrypted storage
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import random
from statistics import mean
from typing import Any

import numpy as np

from app.ml.contrastive_v12 import _partition
from app.ml.hybrid_evaluation import QueryLabel, _metrics, read_benchmark
from app.ml.hybrid_retrieval import SourcePassage, _ordered, _dense_scores, bm25_scores, _tfidf_scores

VERSION = "sentence-transformer-local-triplet-v13.0"
SEED = 132026


@dataclass(frozen=True)
class TrainingConfig:
    epochs: int = 3
    batch_size: int = 4
    lr: float = 2e-5
    margin: float = 0.20
    max_length: int = 192
    device: str = "cpu"

    def validate(self):
        if (type(self.epochs) is not int or not 1 <= self.epochs <= 15
                or type(self.batch_size) is not int or not 1 <= self.batch_size <= 16
                or type(self.max_length) is not int or not 32 <= self.max_length <= 512
                or not math.isfinite(self.lr) or not 1e-7 <= self.lr <= 1e-3
                or not math.isfinite(self.margin) or not 0.02 <= self.margin <= 1.0
                or self.device not in ("cpu", "mps", "cuda")):
            raise ValueError("INVALID_NEURAL_TRAINING_CONFIG")


def explicit_triplets(passages: list[SourcePassage], train: list[QueryLabel]) -> list[tuple[str, str, str]]:
    """Use ONLY judged positives and hard negatives for the same authorized query."""
    indexed = {p.passage_id: p for p in passages}
    triplets: set[tuple[str, str, str]] = set()
    for query in train:
        for pos_id in query.relevant_passage_ids:
            for neg_id in query.hard_negative_passage_ids:
                p, n = indexed[pos_id], indexed[neg_id]
                if (p.organization_id != query.organization_id or
                    n.organization_id != query.organization_id or
                    p.document_id not in query.authorized_documents or
                    n.document_id not in query.authorized_documents or
                    p.text == n.text):
                    raise ValueError("INVALID_TRAINING_EVIDENCE_SCOPE")
                triplets.add((query.requirement, p.text, n.text))
    if len(triplets) < 6:
        raise ValueError("INSUFFICIENT_EXPLICIT_NEURAL_TRIPLETS")
    return sorted(triplets)


def prepare_experiment(dataset: Path, manifest: Path) -> tuple[list[SourcePassage], dict, list, dict]:
    passages, queries = read_benchmark(dataset)
    parts, embargo = _partition(passages, queries, manifest)
    # Identical query text across train/calibration/test is disallowed: family
    # separation alone may not catch copied queries in distinct families.
    seen: dict[str, str] = {}
    for split in ("train", "calibration", "test"):
        for q in parts[split]:
            canonical = ' '.join(q.requirement.casefold().split())
            other = seen.setdefault(canonical, split)
            if other != split:
                raise ValueError("QUERY_TEXT_LEAKAGE")
    # A held-out document can be a *copy* of an annotated training passage.
    # Guard against exact duplicated evidence even when document IDs differ.
    index = {p.passage_id: p for p in passages}
    evidence_seen: dict[str, str] = {}
    for split in ("train", "calibration", "test"):
        for q in parts[split]:
            for pid in q.relevant_passage_ids | q.hard_negative_passage_ids:
                normalized = ' '.join(index[pid].text.casefold().split())
                other = evidence_seen.setdefault(normalized, split)
                if other != split:
                    raise ValueError("PASSAGE_TEXT_LEAKAGE")
    triplets = explicit_triplets(passages, parts["train"])
    return passages, parts, triplets, embargo


def evaluate_encoder(passages: list[SourcePassage], queries: list[QueryLabel], encoder) -> dict:
    """Evaluate exact same tenant-limited universe for all encoders."""
    all_rows: list[dict] = []
    langs: dict[str, list[dict]] = {"fr": [], "en": []}
    for q in queries:
        permitted = [p for p in passages if p.organization_id == q.organization_id
                     and p.document_id in q.authorized_documents]
        if not permitted:
            raise ValueError('EMPTY_PERMITTED_CORPUS')
        ranks = _ordered(_dense_scores(q.requirement, [p.text for p in permitted], encoder), permitted)
        metrics = _metrics(ranks, q, (1, 3, 5))
        all_rows.append(metrics)
        langs[q.language].append(metrics)

    def aggregate(records):
        if not records: return None
        return {"queries": len(records), **{
            key: round(mean(r[key] for r in records), 4)
            for key in ("mrr", "hit_at_1", "recall_at_3", "recall_at_5",
                        "hard_negative_above_first_positive")}}

    return {"all": aggregate(all_rows), "by_language": {
        k: aggregate(rows) for k, rows in langs.items() if rows}}


def evaluate_lexical(passages, queries) -> dict:
    """Public baselines to avoid claiming that fine-tuning necessarily helps."""
    rows = {"bm25": [], "tfidf_char": []}
    for q in queries:
        permitted = [p for p in passages if p.organization_id == q.organization_id
                     and p.document_id in q.authorized_documents]
        for name, scores in (("bm25", bm25_scores(q.requirement,[p.text for p in permitted])),
                             ("tfidf_char", _tfidf_scores(q.requirement,[p.text for p in permitted]))):
            rows[name].append(_metrics(_ordered(scores,permitted),q,(1,3,5)))
    return {name: {"queries": len(seq), "mrr": round(mean(row["mrr"] for row in seq), 4),
                   "hit_at_1": round(mean(row["hit_at_1"] for row in seq), 4)}
            for name,seq in rows.items()}


def checkpoint_better(current: dict, best: dict, *, epoch: int, best_epoch: int) -> bool:
    """Calibrate on held-out validation only; negative exposure breaks ties."""
    def key(row, step):
        return (row["mrr"], -row["hard_negative_above_first_positive"], -step)
    return key(current, epoch) > key(best, best_epoch)


class SafeEncoder:
    """Batched normalized embedding adapter for the existing retrieval pipeline."""
    def __init__(self, model, *, batch_size: int):
        self.model = model
        self.batch_size = batch_size

    def encode(self, texts: list[str]):
        if len(texts) > 10000 or any(not isinstance(s,str) or len(s) > 5000 for s in texts):
            raise ValueError('INVALID_NEURAL_ENCODING_BATCH')
        vectors = self.model.encode(texts, batch_size=self.batch_size,
                                    normalize_embeddings=True, convert_to_numpy=True,
                                    show_progress_bar=False)
        arr = np.asarray(vectors)
        if len(texts) and (arr.ndim != 2 or len(arr) != len(texts) or
                          not np.isfinite(arr).all()):
            raise ValueError('INVALID_NEURAL_ENCODER_OUTPUT')
        return arr


def select_device(requested: str) -> str:
    if requested not in ("auto", "cpu", "mps", "cuda"):
        raise ValueError('INVALID_DEVICE')
    if requested == "cpu":
        return "cpu"
    import torch
    supported = {"mps": bool(torch.backends.mps.is_available()),
                 "cuda": bool(torch.cuda.is_available())}
    if requested == "auto":
        return "mps" if supported["mps"] else "cuda" if supported["cuda"] else "cpu"
    if not supported[requested]:
        raise ValueError("REQUESTED_DEVICE_UNAVAILABLE")
    return requested


def require_local_model(model_dir: Path) -> Path:
    """Never silently fetch model weights or execute arbitrary model code."""
    path = model_dir.expanduser().resolve(strict=True)
    if not path.is_dir() or not (path / 'modules.json').is_file():
        raise ValueError('LOCAL_SENTENCE_TRANSFORMER_REQUIRED')
    return path


def fingerprint_local_model(model_dir: Path) -> str:
    """Content fingerprint over local model configs and weights, not machine path."""
    root = require_local_model(model_dir)
    digest = sha256()
    files = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix in
                   ('.json', '.safetensors', '.bin', '.model', '.txt'))
    if not files or len(files) > 100:
        raise ValueError('INVALID_LOCAL_MODEL_FILES')
    for file in files:
        digest.update(file.relative_to(root).as_posix().encode('utf-8'))
        with file.open('rb') as fh:
            for chunk in iter(lambda: fh.read(1048576), b''):
                digest.update(chunk)
    return digest.hexdigest()


def load_local_model(model_dir: Path, *, device: str, max_length: int):
    from sentence_transformers import SentenceTransformer
    path = require_local_model(model_dir)
    model = SentenceTransformer(str(path), device=device,
                                local_files_only=True, trust_remote_code=False)
    model.max_seq_length = max_length
    return model


def _forward_sentences(model, texts: list[str], device):
    import torch
    import torch.nn.functional as F
    tokens = model.tokenize(texts)
    features = {key: value.to(device) if isinstance(value,torch.Tensor) else value
                for key,value in tokens.items()}
    vectors = model(features)["sentence_embedding"]
    return F.normalize(vectors,dim=-1)


def train_neural(model, triplets, passages, calibration, *, config: TrainingConfig) -> tuple[dict, dict]:
    """Full-parameter fine-tuning with explicitly annotated triplet margin.

    Returns best state snapshot selected *solely* from validation. No test data
    enters this function. The original model can be restored afterwards.
    """
    config.validate()
    import torch
    import torch.nn.functional as F
    device = torch.device(config.device)
    model.to(device)
    model.max_seq_length = config.max_length
    torch.manual_seed(SEED)
    randomizer = random.Random(SEED)
    opt = torch.optim.AdamW(model.parameters(), lr=config.lr)
    model.eval()
    base = evaluate_encoder(passages,calibration, SafeEncoder(model,batch_size=config.batch_size))["all"]
    best = base
    best_epoch = 0
    # Keep a CPU copy of the best model only, not raw CV strings.
    best_state = {k: v.detach().cpu().clone() for k,v in model.state_dict().items()}
    history = [{"epoch":0, "train_loss":None, **base}]
    for epoch in range(1,config.epochs + 1):
        indices = list(range(len(triplets)))
        randomizer.shuffle(indices)
        model.train()
        losses = []
        for start in range(0,len(indices),config.batch_size):
            batch = [triplets[i] for i in indices[start:start+config.batch_size]]
            anchor, pos, neg = zip(*batch)
            qa = _forward_sentences(model,list(anchor),device)
            positive = _forward_sentences(model,list(pos),device)
            negative = _forward_sentences(model,list(neg),device)
            loss = F.relu(config.margin + (qa * negative).sum(dim=1) -
                          (qa * positive).sum(dim=1)).mean()
            if not torch.isfinite(loss).item():
                raise ValueError('NONFINITE_NEURAL_TRAINING_LOSS')
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
            opt.step()
            losses.append(float(loss.detach().cpu()))
        model.eval()
        score = evaluate_encoder(passages,calibration,SafeEncoder(model,batch_size=config.batch_size))["all"]
        history.append({"epoch":epoch,"train_loss":round(mean(losses),6),**score})
        if checkpoint_better(score,best,epoch=epoch,best_epoch=best_epoch):
            best,best_epoch = score,epoch
            best_state = {k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
    model.load_state_dict(best_state)
    model.eval()
    return {"epoch":best_epoch,"calibration":best}, {"epochs":history,
            "loss":"explicit_cosine_triplet_margin","seed":SEED,
            "optimizer":"AdamW","triplet_count":len(triplets),
            "samples_are_human_annotated_only":True}


def research_run(dataset: Path, manifest: Path, *, local_model: Path | None = None,
                 output: Path | None = None, checkpoint: Path | None = None,
                 config: TrainingConfig | None = None, dry_run: bool = False) -> dict:
    """Offline research experiment. --dry-run needs NO transformers installation."""
    if output is not None and output.exists():
        raise FileExistsError('RESEARCH_REPORT_ALREADY_EXISTS')
    if checkpoint is not None and checkpoint.exists():
        raise FileExistsError('NEURAL_CHECKPOINT_ALREADY_EXISTS')
    passages, parts, triples, embargo = prepare_experiment(dataset,manifest)
    config = config or TrainingConfig()
    config.validate()
    digest = {"dataset_sha256": sha256(dataset.read_bytes()).hexdigest(),
              "manifest_sha256":sha256(manifest.read_bytes()).hexdigest()}
    report: dict[str,Any] = {"version":VERSION, "research_only":True,
             "eligible_for_recruitment_inference":False,
             "makes_recruitment_decisions":False,
             "offline_model_only":True, "pretrained_encoder_finetune": not dry_run,
             "splits":{k:len(v) for k,v in parts.items()},
             "triplets":len(triples),"embargo":embargo,
             "device":config.device,"max_length":config.max_length,
             "data_integrity":digest,
             "privacy_notice":"Trained weights may memorize personal data; keep private, never publish CV-trained checkpoints.",
             "limitations":"Tiny synthetic benchmark and shared retrieval universe are not a valid real-CV evaluation. Model cosine is not proof of competence."}
    if dry_run:
        report["status"] = "validated_dataset_only_no_neural_model_executed"
    else:
        if local_model is None:
            raise ValueError('LOCAL_MODEL_PATH_REQUIRED')
        model = load_local_model(local_model,device=config.device,max_length=config.max_length)
        original = evaluate_encoder(passages,parts["calibration"],SafeEncoder(model,batch_size=config.batch_size))
        selection, history = train_neural(model,triples,passages,parts["calibration"],config=config)
        tuned_calibration = evaluate_encoder(passages,parts["calibration"],SafeEncoder(model,batch_size=config.batch_size))
        # Held-out test is evaluated ONCE after model selection on validation.
        tuned_test = evaluate_encoder(passages,parts["test"],SafeEncoder(model,batch_size=config.batch_size))
        report.update({"status":"trained_locally_evaluated_research_only",
                       "model_source_fingerprint_sha256": fingerprint_local_model(local_model),
                       "selected":selection,"training":history,
                       "calibration_original":original,
                       "calibration_selected":tuned_calibration,
                       "heldout_test":{"neural_selected":tuned_test,
                                       "lexical_baselines":evaluate_lexical(passages,parts["test"])}})
        if checkpoint:
            checkpoint.parent.mkdir(parents=True,exist_ok=True)
            model.save(str(checkpoint))
            report["checkpoint_written_locally"] = True
    if output:
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return report
