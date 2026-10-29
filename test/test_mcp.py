import unittest
from unittest.mock import patch
from api.mcp import dispatch
from reeldrop_media import MediaError

class MCPTests(unittest.TestCase):
    def test_initialize_and_tool_list(self):
        result=dispatch({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2026-07-28'}})
        self.assertEqual(result['result']['protocolVersion'],'2026-07-28')
        self.assertEqual(len(dispatch({'jsonrpc':'2.0','id':2,'method':'tools/list'})['result']['tools']),2)
        self.assertIsNone(dispatch({'jsonrpc':'2.0','method':'notifications/initialized'}))
    def test_tool_payload_and_access_error(self):
        with patch('api.mcp.extract_payload',return_value={'media':[{'type':'image'}]}):
            result=dispatch({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'get_instagram_media','arguments':{'url':'https://instagram.com/p/ABCDE/'}}})
        self.assertFalse(result['result']['isError'])
        with patch('api.mcp.extract_payload',side_effect=MediaError('Public content unavailable')):
            result=dispatch({'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'get_instagram_profile','arguments':{'username':'creator'}}})
        self.assertTrue(result['result']['isError'])
    def test_unknown_tools_do_not_execute(self):
        result=dispatch({'jsonrpc':'2.0','id':5,'method':'tools/call','params':{'name':'private_account_download'}})
        self.assertEqual(result['error']['code'],-32602)
