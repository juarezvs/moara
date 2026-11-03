import io,zipfile,unittest
from moara.gateway.xlsx_documents import extract

def workbook(sheet,extra=None):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as z:
        for name,content in {'[Content_Types].xml':'<Types/>',
            'xl/workbook.xml':'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Prazos" r:id="rId1"/></sheets></workbook>',
            'xl/_rels/workbook.xml.rels':'<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/></Relationships>',
            'xl/worksheets/sheet1.xml':sheet,**(extra or {})}.items():z.writestr(name,content)
    return output.getvalue()

class XlsxTests(unittest.TestCase):
    def test_cells_preserve_coordinates_and_formula_cache_is_explicit(self):
        raw=workbook('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="A1" t="inlineStr"><is><t>Prazo</t></is></c><c r="C1"><f>SUM(A2:A9)</f><v>9</v></c></row></sheetData></worksheet>')
        text=extract(raw)[0]['text'];self.assertIn('A1=Prazo',text);self.assertIn('C1=',text);self.assertIn('valor em cache: 9',text);self.assertNotIn('SUM(',text)
    def test_external_relationship_cannot_trigger_fetch(self):
        raw=workbook('<worksheet/>',{'xl/worksheets/_rels/sheet1.xml.rels':'<Relationships><Relationship TargetMode="External" Target="https://example.invalid/private"/></Relationships>'})
        with self.assertRaisesRegex(ValueError,'external_relationship'):extract(raw)
    def test_xml_entities_and_oversized_archives_rejected(self):
        raw=workbook('<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]><worksheet/>')
        with self.assertRaisesRegex(ValueError,'declaration_forbidden'):extract(raw)
        raw=workbook('<worksheet/>',{'xl/large.bin':b'0'*(33*1024**2)})
        with self.assertRaisesRegex(ValueError,'archive_limit'):extract(raw)
    def test_macros_rejected(self):
        with self.assertRaisesRegex(ValueError,'active_content'):extract(workbook('<worksheet/>',{'xl/vbaProject.bin':'x'}))
