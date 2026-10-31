from test_auth import authenticate


def headers(client):
    return {'Authorization': 'Bearer ' + authenticate(client).json()['access_token']}


def test_candidate_search_is_tenant_scoped(client_and_orgs):
    client, _ = client_and_orgs
    h = headers(client)
    for name in ['Aline Kazadi', 'Jean Mutombo', 'Aline Kabeya']:
        r = client.post('/api/v1/candidates', headers=h, json={'full_name':name})
        assert r.status_code == 201, r.text
    matching = client.get('/api/v1/candidates', headers=h, params={'q':'Aline', 'limit':25})
    assert matching.status_code == 200, matching.text
    assert matching.json()['total'] == 2
    assert all('Aline' in p['full_name'] for p in matching.json()['items'])
    escaped = client.get('/api/v1/candidates', headers=h, params={'q':'%', 'limit':25})
    assert escaped.status_code == 200
    assert escaped.json()['total'] == 0
    assert client.get('/api/v1/candidates', headers=h, params={'q':'x'*121}).status_code == 422


def test_editing_job_invalidates_confirmation(client_and_orgs):
    client, _ = client_and_orgs
    h = headers(client)
    r = client.post('/api/v1/jobs', headers=h, json={
        'title':'Développeur API Python',
        'description':'Construire des interfaces et des API robustes.'})
    assert r.status_code == 201, r.text
    jid = r.json()['id']
    items = [{'code':'PYTHON', 'label':'Python', 'category':'skill', 'required':True,
              'weight':4,'justification':'Code backend nécessaire'}]
    assert client.put(f'/api/v1/jobs/{jid}/requirements', headers=h, json={'items':items}).status_code == 200
    assert client.post(f'/api/v1/jobs/{jid}/requirements/confirm', headers=h,
                       json={'expected_version':1}).status_code == 200
    edited = client.patch(f'/api/v1/jobs/{jid}', headers=h,
                          json={'description':'Concevoir, vérifier et maintenir des API Python.'})
    assert edited.status_code == 200, edited.text
    assert edited.json()['criteria_confirmed_at'] is None
    assert edited.json()['status'] == 'draft'
    assert client.post('/api/v1/campaigns', headers=h,
                       json={'name':'Campagne 1','job_id':jid}).status_code == 409
