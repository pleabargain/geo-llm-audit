import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:8822/api/audit', data=json.dumps({'url':'https://dgdedge.com'}).encode(), headers={'Content-Type':'application/json'})
r = urllib.request.urlopen(req)
d = json.loads(r.read())
print('keys:', list(d.keys()))
print('score:', d['score'])
print('recs:', d.get('recommendations'))
print('homepage keys:', list(d['checks']['homepage'].keys()))
