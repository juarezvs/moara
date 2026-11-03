import unittest
from fastapi import HTTPException
from moara.gateway.context_budget import fit,input_size,prefix_notice

class ContextBudgetTests(unittest.TestCase):
    def test_current_question_and_source_are_preserved_when_old_history_is_omitted(self):
        source='<context><source id="1">'+'Documento completo. '*400+'</source></context>'
        latest={'role':'user','content':'Analise o processo anexo e verifique o que devo fazer.\n'+source}
        messages=[{'role':'system','content':'Política obrigatória. '*200},
            {'role':'user','content':'Histórico anterior. '*2000},{'role':'assistant','content':'Resposta antiga. '*1500},latest]
        kept,output,info,notice=fit(messages,None,8192,768,True)
        self.assertEqual(kept[-1],latest)
        self.assertIn('Política obrigatória.',kept[0]['content'])
        self.assertEqual(info['omitted_messages'],2)
        self.assertFalse(info['current_input_truncated'])
        self.assertIn('continuam no histórico',notice)
        self.assertLessEqual(input_size(kept,None),(8192-output)*3)
        self.assertEqual(messages[0]['content'],'Política obrigatória. '*200)

    def test_excessive_output_reservation_is_reduced_without_omitting_inputs(self):
        messages=[{'role':'system','content':'Política.'},{'role':'user','content':'Dado. '*2500}]
        kept,output,info,notice=fit(messages,None,8192,4096)
        self.assertEqual(kept,messages);self.assertLess(output,4096)
        self.assertEqual(info['omitted_messages'],0);self.assertTrue(notice)

    def test_oversized_current_source_is_not_silently_cut(self):
        messages=[{'role':'system','content':'Política'},{'role':'user','content':'Documento '*10000}]
        with self.assertRaises(HTTPException) as error:fit(messages,None,8192,512,True)
        self.assertEqual(error.exception.status_code,413)
        self.assertIn('nenhum texto foi cortado',error.exception.detail)
        self.assertEqual(messages[-1]['content'],'Documento '*10000)

    def test_plain_chat_does_not_discard_older_facts_automatically(self):
        messages=[{'role':'system','content':'Política'},{'role':'user','content':'Fatos '*15000},{'role':'assistant','content':'Ok'},{'role':'user','content':'E o segundo ponto?'}]
        with self.assertRaises(HTTPException):fit(messages,None,8192,512,False)

    def test_normal_request_is_unchanged(self):
        messages=[{'role':'system','content':'Política'},{'role':'user','content':'Explique uma API'}]
        kept,output,info,notice=fit(messages,None,8192,512)
        self.assertEqual(kept,messages);self.assertEqual(output,512);self.assertFalse(notice)

    def test_notice_is_included_in_text_for_clients_that_do_not_render_metadata(self):
        result={'choices':[{'message':{'content':'Resposta com fonte [D1].'}}]}
        self.assertEqual(prefix_notice(result,'Aviso.\n\n')['choices'][0]['message']['content'],'Aviso.\n\nResposta com fonte [D1].')
