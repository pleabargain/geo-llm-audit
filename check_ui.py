import urllib.request
r = urllib.request.urlopen('http://127.0.0.1:8765/')
h = r.read().decode()
print('results div:', '<div id="results"' in h)
print('render func:', 'function render(d)' in h)
print('recommendations:', 'Recommendations to improve' in h)
print('length:', len(h))
