"""Bounded OOXML reading only: no formulas, macros or external requests execute."""
import csv,io,posixpath,re,zipfile
from xml.etree import ElementTree as ET
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}

def archive(raw):
    z=zipfile.ZipFile(io.BytesIO(raw) if isinstance(raw,(bytes,bytearray)) else raw);infos=z.infolist();names=[i.filename for i in infos]
    if len(infos)>3000 or sum(i.file_size for i in infos)>32*1024**2 or len(set(names))!=len(names):raise ValueError('xlsx_archive_limit')
    if not {'xl/workbook.xml','xl/_rels/workbook.xml.rels','[Content_Types].xml'}<=set(names):raise ValueError('invalid_xlsx')
    for i in infos:
        if i.flag_bits&1 or i.filename.startswith('/') or '..' in i.filename.split('/') or '\\' in i.filename:raise ValueError('invalid_xlsx_archive')
        if any(marker in i.filename.lower() for marker in ['vbaproject','externallinks/','embeddings/','connections.xml']):raise ValueError('unsupported_xlsx_active_content')
    return z

def xml(z,name):
    raw=z.read(name)
    if b'<!doctype' in raw.lower() or b'<!entity' in raw.lower():raise ValueError('xlsx_xml_declaration_forbidden')
    return ET.fromstring(raw)

def extract(raw):
    with archive(raw) as z:
        for name in z.namelist():
            if name.endswith('.rels'):
                if any(row.get('TargetMode','').lower()=='external' for row in xml(z,name)):raise ValueError('xlsx_external_relationship_forbidden')
        workbook=xml(z,'xl/workbook.xml');sheets=workbook.findall('s:sheets/s:sheet',NS)
        if not 1<=len(sheets)<=30:raise ValueError('xlsx_sheet_limit')
        relations={row.get('Id'):row.get('Target','') for row in xml(z,'xl/_rels/workbook.xml.rels')
            if row.get('Type','').endswith('/worksheet')}
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            for item in xml(z,'xl/sharedStrings.xml').findall('s:si',NS):
                strings.append(''.join(item.itertext()))
                if len(strings)>100000 or len(strings[-1])>50000:raise ValueError('xlsx_string_limit')
        pages=[];cells=0;total=0
        for sheet in sheets:
            target=relations.get(sheet.get('{'+NS['r']+'}id'))
            if not target:raise ValueError('invalid_xlsx_sheet_relation')
            target=posixpath.normpath(target.lstrip('/') if target.startswith('/') else 'xl/'+target)
            if not target.startswith('xl/worksheets/'):raise ValueError('invalid_xlsx_sheet_target')
            rows=xml(z,target).findall('s:sheetData/s:row',NS)
            if len(rows)>10000:raise ValueError('xlsx_row_limit')
            output=io.StringIO();output.write('Planilha: '+sheet.get('name','Sem nome')+'\nValores originais; fórmulas não são executadas nem recalculadas.\n')
            writer=csv.writer(output)
            for row in rows:
                result=[];rowcells=row.findall('s:c',NS)
                if len(rowcells)>100:raise ValueError('xlsx_column_limit')
                for cell in rowcells:
                    cells+=1
                    if cells>150000:raise ValueError('xlsx_cell_limit')
                    address=cell.get('r','')
                    if not re.fullmatch(r'[A-Z]{1,3}[1-9][0-9]{0,6}',address):raise ValueError('invalid_xlsx_cell_address')
                    kind=cell.get('t');value=cell.findtext('s:v','',NS)
                    if kind=='s':value=strings[int(value)]
                    elif kind=='inlineStr':value=''.join(cell.find('s:is',NS).itertext()) if cell.find('s:is',NS) is not None else ''
                    if cell.find('s:f',NS) is not None:value='[fórmula não executada; valor em cache: '+value+']'
                    if len(value)>50000:raise ValueError('xlsx_cell_size_limit')
                    result.append(address+'='+value)
                writer.writerow(result)
                if output.tell()>1000000:raise ValueError('xlsx_text_limit')
            text=output.getvalue();total+=len(text)
            if total>1000000:raise ValueError('xlsx_text_limit')
            if rows:pages.append({'page':None,'text':text})
        return pages
