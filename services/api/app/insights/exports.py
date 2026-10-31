"""Documentary coverage exports. No final hiring recommendation or demographic attributes."""
import csv
from io import BytesIO, StringIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pathlib import Path
import xlsxwriter

def report_font():
    path=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if path.exists():
        if 'TalentDejaVu' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('TalentDejaVu',str(path)))
        return 'TalentDejaVu'
    return 'Helvetica'

COLUMNS=['Référence dossier','Candidature','Couverture /100','État','Mentions documentées',
         'À vérifier','Non retrouvées','Revue humaine']
RANKED_COLUMNS=['Rang','Référence dossier','Candidature','Correspondance pondérée (%)',
                'Poids évalué (%)','État','Mentions documentées','À vérifier','Non retrouvées','Revue humaine']
RANKING_NOTE='Classement décroissant sur les mêmes critères évalués. Les critères non évalués restent à vérifier. Les ex æquo partagent le même rang.'

def safe_cell(value):
    """Prevent spreadsheet formula execution, including leading whitespace bypasses."""
    s='' if value is None else str(value)
    if s.lstrip().startswith(('=','+','-','@')) or s[:1] in ('\t','\r','\n'):
        return "'"+s
    return s


def csv_bytes(rows, *, columns=COLUMNS):
    out=StringIO(newline='')
    writer=csv.writer(out,delimiter=';')
    writer.writerow(columns)
    for row in rows: writer.writerow([safe_cell(c) for c in row])
    return ('\ufeff'+out.getvalue()).encode('utf-8')


def xlsx_bytes(rows, title, *, columns=COLUMNS):
    out=BytesIO()
    wb=xlsxwriter.Workbook(out,{'in_memory':True})
    sheet=wb.add_worksheet('Classement' if columns==RANKED_COLUMNS else 'Couverture')
    title_style=wb.add_format({'bold':True,'font_size':16,'font_color':'#173A65'})
    header=wb.add_format({'bold':True,'bg_color':'#143B6A','font_color':'#FFFFFF',
                          'text_wrap':True,'valign':'vcenter','border':0})
    normal=wb.add_format({'text_wrap':True,'valign':'top'})
    number=wb.add_format({'num_format':'0.00','valign':'top'})
    sheet.write_string(0,0,safe_cell(title),title_style)
    sheet.write_string(1,0,RANKING_NOTE if columns==RANKED_COLUMNS else 'Un score non calculable signale des critères non évalués, pas zéro. Aucune décision automatique.')
    for col,name in enumerate(columns): sheet.write_string(3,col,name,header)
    sheet.set_row(3,30)
    for index,row in enumerate(rows,start=4):
        for col,value in enumerate(row):
            if isinstance(value,(float,int)):
                sheet.write_number(index,col,value,number if isinstance(value,float) else normal)
            else:
                sheet.write_string(index,col,safe_cell(value),normal)
    sheet.set_column(0,0,22);sheet.set_column(1,1,37);sheet.set_column(2,2,22)
    sheet.set_column(3,7,22)
    if columns==RANKED_COLUMNS:
        sheet.set_column(0,0,9);sheet.set_column(1,1,25);sheet.set_column(2,2,37)
        sheet.set_column(3,4,24);sheet.set_column(5,9,23)
    sheet.freeze_panes(4,0)
    if rows: sheet.autofilter(3,0,len(rows)+3,len(columns)-1)
    wb.close()
    return out.getvalue()


def pdf_bytes(rows,title, *, columns=COLUMNS):
    out=BytesIO()
    document=SimpleDocTemplate(out,pagesize=landscape(A4),leftMargin=32,rightMargin=32,
                               topMargin=35,bottomMargin=34)
    styles=getSampleStyleSheet()
    font=report_font()
    small=ParagraphStyle('row_small',parent=styles['BodyText'],fontName=font,fontSize=7,
                         leading=9,wordWrap='CJK')
    heading=ParagraphStyle('export_heading',parent=styles['Heading1'],fontName=font,textColor=colors.HexColor('#143B6A'))
    blocks=[Paragraph(escape(title),heading),Spacer(1,8),
            Paragraph(escape(RANKING_NOTE) if columns==RANKED_COLUMNS else 'Score non calculable = vérification nécessaire, jamais zéro. Aucune décision automatisée.',small),Spacer(1,15)]
    headings=columns if columns==RANKED_COLUMNS else ['Dossier','Candidature','Couverture','État','Documentées','À revoir','Non trouvées','Revue humaine']
    data=[[Paragraph(escape(c),small) for c in headings]]
    for row in rows:
        data.append([Paragraph(escape(safe_cell(
            format(value,'g').replace('.',',') if columns==RANKED_COLUMNS and isinstance(value,float)
            else value)[:110]),small) for value in row])
    widths=([50,80,110,78,58,100,65,50,70,110] if columns==RANKED_COLUMNS else [79,137,67,88,75,64,75,115])
    table=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8eef5')),
      ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#e5e7eb')),
      ('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),
      ('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    blocks.append(table)
    document.build(blocks)
    return out.getvalue()
