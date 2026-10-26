import base64
import io
import json
import warnings

from PIL import Image, ImageOps

import core

def preprocess(value):
    if ',' in value and value.startswith('data:'):
        value = value.split(',', 1)[1]
    if len(value) > 2800000:
        raise ValueError('Envie imagem de até 2 MB')
    raw = base64.b64decode(value, validate=True)
    Image.MAX_IMAGE_PIXELS = 12000000
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        image = Image.open(io.BytesIO(raw))
        if image.format not in ('PNG', 'JPEG', 'WEBP'):
            raise ValueError('Use PNG, JPEG ou WebP')
        image.load()
    image = ImageOps.exif_transpose(image).convert('RGB')
    image.thumbnail((1024, 1024))
    output = io.BytesIO()
    image.save(output, format='PNG', optimize=True)
    if len(output.getvalue()) > 1024 * 1024:
        image.thumbnail((768, 768))
        output = io.BytesIO()
        image.save(output, format='PNG', optimize=True)
    return base64.b64encode(output.getvalue()).decode()

async def analyze(prompt, images):
    prepared = [preprocess(image) for image in images]
    return await core.gateway('/v1/vision/analyze', {'prompt': prompt, 'images': prepared})

async def run(job, progress):
    data = job['input']
    await progress('Validando e reduzindo as imagens', 15)
    await progress('Analisando com o Gemma 4 multimodal local', 35)
    prompt = data['prompt']
    if len(data.get('images', [])) == 2:
        prompt = 'Compare as duas imagens. Separe diferenças observadas e sugestões. ' + prompt
    result = await analyze(prompt, data['images'])
    path = core.job_directory(job['id'])
    (path / 'analysis.md').write_text(result['analysis'], encoding='utf-8')
    (path / 'vision-metadata.json').write_text(json.dumps({'model': result['model'], 'images': len(data['images'])}, indent=2))
    return {'summary': 'Análise visual concluída', 'text': result['analysis'],
        'artifacts': ['analysis.md', 'vision-metadata.json'], 'metadata': {'model': result['model']}}
