"""Offline owned-container controls for the inline Web image producer gate."""
import ast
from pathlib import Path
import textwrap
import unittest

workflow=(Path(__file__).resolve().parents[1]/'.github/workflows/publish-image.yml').read_text(encoding='utf-8')
segment=workflow.split('      - name: Verify packaged Web assets and source revision\n',1)[1].split('\n      - name: Scan the built image before publication',1)[0]
script=textwrap.dedent(segment.split('        run: |\n',1)[1])
tree=ast.parse(script)
functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in ('verify_owned_container','release_owned_container')]
if len(functions)!=2:raise RuntimeError('Expected exact producer custody functions')
import re
context={'re':re}
exec(compile(ast.fix_missing_locations(ast.Module(body=functions,type_ignores=[])),'<producer-custody>','exec'),context)
ID='a'*64
NAME='legacy-web-assets-check-'+'b'*32
IMAGE='sha256:'+'c'*64

class Controls(unittest.TestCase):
    def verify(self, responses):
        calls=[]
        def native(args):
            calls.append(args)
            response=responses.pop(0)
            if isinstance(response,Exception):raise response
            return response
        context['native']=native
        return calls
    def test_exact_id_removal_and_daemon_absence(self):
        calls=self.verify([f'{ID}|/{NAME}|{IMAGE}|created',ID,'daemon',''])
        context['release_owned_container'](ID,NAME,IMAGE)
        self.assertEqual(['container','rm','--force',ID],calls[1])
        self.assertEqual(['container','ls','--all','--no-trunc','--quiet','--filter','id='+ID],calls[3])
    def test_bad_identity_or_non_created_state_never_removes(self):
        for identity in (f'{ID}|/other|{IMAGE}|created',f'{ID}|/{NAME}|{IMAGE}|exited',f'{ID}|/{NAME}|sha256:'+('d'*64)+'|created'):
            with self.subTest(identity=identity):
                calls=self.verify([identity])
                with self.assertRaises(ValueError):context['release_owned_container'](ID,NAME,IMAGE)
                self.assertEqual(1,len(calls))
        calls=self.verify([])
        with self.assertRaises(ValueError):context['release_owned_container']('bad',NAME,IMAGE)
        self.assertEqual([],calls)
    def test_remove_failure_daemon_unavailable_or_id_present_fail(self):
        identity=f'{ID}|/{NAME}|{IMAGE}|created'
        for responses in ([identity,RuntimeError('rm failed')],[identity,ID,RuntimeError('daemon down')],
                          [identity,ID,'daemon',ID],[identity,ID,'']):
            with self.subTest(responses=len(responses)):
                self.verify(list(responses))
                with self.assertRaises((ValueError,RuntimeError)):context['release_owned_container'](ID,NAME,IMAGE)
    def test_gate_retains_asset_and_revision_contracts(self):
        for fragment in ('len(required)','len(fonts)','object_pairs_hook=unique_object',
                         'label != revision','sourceRevision','assetCount','fontCount'):
            self.assertIn(fragment,script)
        self.assertIn('"export", "--output", archive, container_id',script)
        self.assertIn('inspectionContainerCleanup="settled"',script)

if __name__=='__main__':unittest.main()
