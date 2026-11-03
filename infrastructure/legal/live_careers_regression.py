import pathlib
root=pathlib.Path(__file__).resolve().parents[2]
source=(root/'infrastructure/legal/live_google_app.py').read_text().replace("root/'tmp/google-discovery-stage.json'","root/'tmp/careers-stage.json'").replace('google-app-public.json','careers-regression-public.json').replace('google-app-stage.json','careers-regression-stage.json')
exec(compile(source,'live_careers_regression','exec'),{'__file__':str(root/'infrastructure/legal/live_google_app.py')})
