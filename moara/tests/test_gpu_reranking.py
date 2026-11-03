import unittest
from unittest.mock import patch, AsyncMock
from moara.gateway import platform_runs


class RankingRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def result(self):
        return {'query':'Prazo fictício?', 'matches':[
            {'id':'one','text':'Primeiro trecho autorizado.','citation':'[1]'},
            {'id':'two','text':'Segundo trecho autorizado.','citation':'[2]'}]}

    async def test_single_authorized_match_needs_no_model_ranking(self):
        result=self.result();result['matches']=result['matches'][:1]
        with patch.object(platform_runs,'model_text',AsyncMock(side_effect=AssertionError('unnecessary inference'))):
            value=await platform_runs.rerank(None,None,result)
        self.assertEqual(value['matches'][0]['id'],'one')
        self.assertEqual(value['reranker'],'not_needed_single_match')

    async def test_invalid_model_ranking_retains_authorized_hybrid_results(self):
        with patch.object(platform_runs,'model_text',AsyncMock(return_value='[1, 1]')):
            value=await platform_runs.rerank(None,None,self.result())
        self.assertEqual([row['id'] for row in value['matches']],['one','two'])
        self.assertEqual(value['reranker'],'hybrid_retained_invalid_model_ranking')

    async def test_valid_ranking_reorders_and_renumbers_citations(self):
        with patch.object(platform_runs,'model_text',AsyncMock(return_value='```json\n[2, 1]\n```')):
            value=await platform_runs.rerank(None,None,self.result())
        self.assertEqual([row['id'] for row in value['matches']],['two','one'])
        self.assertEqual([row['citation'] for row in value['matches']],['[1]','[2]'])


if __name__=='__main__':unittest.main()
