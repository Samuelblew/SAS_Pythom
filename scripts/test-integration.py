"""Integration checks against a running Docker stack; Python standard library only."""
import argparse
import json
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:5173')
    parser.add_argument('--state-file')
    parser.add_argument('--verify-state', action='store_true')
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    tenant = None
    checks = 0

    def request(method, path, body=None, expected=200, tenant_id=None):
        nonlocal checks
        headers = {'Content-Type': 'application/json'}
        if tenant_id or tenant:
            headers['X-Tenant-Id'] = tenant_id or tenant
        req = Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                      headers=headers, method=method)
        try:
            response = urlopen(req, timeout=20)
        except HTTPError as exc:
            response = exc
        with response:
            data = response.read().decode()
            assert response.code == expected, f'{method} {path}: {response.code}, expected {expected}: {data}'
        checks += 1
        print(f'OK {method} {path} [{expected}]', flush=True)
        try:
            return json.loads(data)
        except ValueError:
            return data

    if args.verify_state:
        state = json.loads(Path(args.state_file).read_text())
        saved = request('GET', '/api/v1/tenants/' + state['id'])
        assert saved['name'] == state['name']
        print('PASS: data created before restart is still persisted in MySQL.')
        return

    html = request('GET', '/')
    assert '<div id="root">' in html
    for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html):
        request('GET', asset)
    request('GET', '/people')
    request('GET', '/swagger')
    schema = request('GET', '/swagger/v1/swagger.json')
    assert '/api/v1/allocations' in schema['paths']
    assert request('GET', '/api/v1/health')['database'] == 'connected'
    request('GET', '/api/v1/people', expected=400)
    tenant_record = request('POST', '/api/v1/tenants', {'name': 'Integration ' + str(uuid4())}, 201)
    tenant = tenant_record['id']
    assert request('GET', '/api/v1/tenants/' + tenant)['name'] == tenant_record['name']
    if args.state_file:
        Path(args.state_file).write_text(json.dumps(tenant_record))
    other = request('POST', '/api/v1/tenants', {'name': 'Isolation ' + str(uuid4())}, 201)['id']
    client = request('POST', '/api/v1/clients', {'name': 'Test client'}, 201)
    skill = request('POST', '/api/v1/skills', {'name': 'Python'}, 201)
    person_body = {'name': 'Integration person', 'weeklyCapacityHours': 40,
                   'status': 'Active', 'hourlyCost': 100, 'seniority': 'Senior'}
    person = request('POST', '/api/v1/people', person_body, 201)
    assert request('GET', f'/api/v1/people/{person["id"]}')['name'] == person_body['name']
    request('POST', f'/api/v1/people/{person["id"]}/skills',
            {'skillId': skill['id'], 'level': 'Expert'}, 201)
    project = request('POST', '/api/v1/projects', {
        'name': 'Integration project', 'clientId': client['id'], 'status': 'InProgress',
        'priority': 'High', 'startDate': '2026-10-26', 'endDate': '2026-11-01',
        'estimatedRevenue': 10000}, 201)
    allocation_body = {'personId': person['id'], 'projectId': project['id'],
                       'role': 'Developer', 'dedicationPercent': 60,
                       'startDate': '2026-10-26', 'endDate': '2026-11-01', 'status': 'Confirmed'}
    allocation = request('POST', '/api/v1/allocations', allocation_body, 201)
    assert request('GET', f'/api/v1/allocations/{allocation["id"]}')['dedicationPercent'] == 60
    request('POST', '/api/v1/allocations', {**allocation_body, 'dedicationPercent': 50}, 409)
    period = '?from=2026-10-26&to=2026-11-01'
    capacity = request('GET', f'/api/v1/capacity/people/{person["id"]}/availability' + period)
    assert capacity['weeks'][0]['allocatedPercent'] == 60
    assert capacity['weeks'][0]['availableHours'] == 16
    people = request('GET', f'/api/v1/projects/{project["id"]}/people')['people']
    assert any(p['personId'] == person['id'] for p in people)
    request('GET', '/api/v1/financials/overview' + period)
    assert request('GET', '/api/v1/audit-logs')['totalCount'] > 0
    request('GET', f'/api/v1/people/{person["id"]}', expected=404, tenant_id=other)
    assert request('GET', '/api/v1/people', tenant_id=other)['totalCount'] == 0
    updated = request('PUT', f'/api/v1/people/{person["id"]}', {**person_body, 'name': 'Updated person'})
    assert updated['name'] == 'Updated person'
    assert request('GET', f'/api/v1/people/{person["id"]}')['name'] == 'Updated person'
    request('DELETE', f'/api/v1/allocations/{allocation["id"]}', expected=204)
    request('GET', f'/api/v1/allocations/{allocation["id"]}', expected=404)
    capacity = request('GET', f'/api/v1/capacity/people/{person["id"]}/availability' + period)
    assert capacity['weeks'][0]['allocatedPercent'] == 0
    for resource, item in [('projects', project), ('people', person), ('skills', skill), ('clients', client)]:
        request('DELETE', f'/api/v1/{resource}/{item["id"]}', expected=204)
    print(f'PASS: {checks} HTTP checks plus business assertions. Test tenants: {tenant}, {other}')


if __name__ == '__main__':
    main()
