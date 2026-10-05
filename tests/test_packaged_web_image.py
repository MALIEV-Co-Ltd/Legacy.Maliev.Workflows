"""Execute the actual publisher gate against owned scratch images, never start them."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'a' * 40
# Independent inventory from Web007c manifest and consumer route selection.
MANIFEST = {
    'scripts': ['vendor.min.js', 'app.min.js'],
    'routeScripts': ['route-inquiry.js', 'route-error.js', 'route-instant-quotation.js', 'route-member-order.js',
                     'route-service-finder.js', 'route-service-cnc.js', 'route-service-finishing.js',
                     'route-service-printing.js', 'route-service-scanning.js', 'route-service-toc.js'],
    'routeScopedModules': {'instantQuotationViewer': 'instant-quotation-viewer.mjs',
                          'instantQuotationWorkflow': 'instant-quotation-workflow.mjs'},
    'styles': ['site.min.css'],
    'routeStyles': ['route-about.css', 'route-home.css', 'route-inquiry.css', 'route-error.css',
                    'route-instant-quotation.css', 'route-services.css', 'route-services-index.css'],
}
ASSETS = (MANIFEST['scripts'] + MANIFEST['routeScripts'] + list(MANIFEST['routeScopedModules'].values())
          + MANIFEST['styles'] + MANIFEST['routeStyles'])
FONT_NAMES = [f'{family}-{weight}-normal-SYNTHETIC.woff2' for family in ('outfit-latin', 'noto-sans-thai-thai')
              for weight in ('400', '500', '600')]
FONT_NAMES += ['fa-brands-400-SYNTHETIC.woff2', 'fa-regular-400-SYNTHETIC.woff2',
               'fa-solid-900-SYNTHETIC.woff2', 'fa-v4compatibility-SYNTHETIC.woff2']
FONT_PATHS = ['dist/assets/' + name for name in FONT_NAMES]
FONT_PATHS += ['lib/outfit/outfit-latin-400-normal.woff2', 'lib/ibm-plex/NotoSansThai-Regular.woff2']


def gate_script():
    workflow = (ROOT / '.github/workflows/publish-image.yml').read_text(encoding='utf-8')
    block = workflow.split('      - name: Verify packaged Web assets and source revision\n', 1)[1]
    return textwrap.dedent(block.split('        run: |\n', 1)[1].split('\n      - name:', 1)[0])


def docker(*arguments):
    result = subprocess.run(['docker', *arguments], capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise AssertionError('Owned scratch fixture Docker operation failed')
    return result.stdout.strip()


def execute(image, revision=REVISION, repository='MALIEV-Co-Ltd/Legacy.Maliev.Web',
            dockerfile='Legacy.Maliev.Web/Dockerfile'):
    environment = dict(os.environ, BUILT_IMAGE=image, EXPECTED_SOURCE_REVISION=revision,
                       CALLER_REPOSITORY=repository, SOURCE_DOCKERFILE=dockerfile)
    return subprocess.run([os.environ.get('PYTHON', 'python3'), '-B', '-'], input=gate_script(),
                          capture_output=True, text=True, env=environment, timeout=120)


class WebImageTests(unittest.TestCase):
    def with_image(self, callback, broken=None, empty=False, label=REVISION, manifest=None, css=None):
        image = 'legacy-web-gate-fixture:' + uuid.uuid4().hex
        built = False
        with tempfile.TemporaryDirectory(prefix='legacy-web-gate-fixture-') as directory:
            root = Path(directory)
            files = {'dist/' + name: b'synthetic generated asset' for name in ASSETS}
            files.update({path: b'synthetic local font' for path in FONT_PATHS})
            files['dist/asset-manifest.json'] = (manifest or json.dumps(MANIFEST)).encode()
            files['dist/site.min.css'] = (css if css is not None else ''.join(
                f'@font-face{{src:url("./assets/{name}")}}' for name in FONT_NAMES)).encode()
            files['dist/route-error.css'] = b'@font-face{src:url(/lib/outfit/outfit-latin-400-normal.woff2)}@font-face{src:url(/lib/ibm-plex/NotoSansThai-Regular.woff2)}'
            for name, content in files.items():
                if name == broken and not empty:
                    continue
                path = root / 'wwwroot' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'' if name == broken else content)
            label_line = '' if label is None else f'LABEL org.opencontainers.image.revision="{label}"\n'
            (root / 'Dockerfile').write_text('FROM scratch\n' + label_line +
                'COPY wwwroot /app/wwwroot/\nENTRYPOINT ["/application-must-not-start"]\n')
            try:
                docker('build', '--network', 'none', '--quiet', '--tag', image, str(root))
                built = True
                callback(image)
                self.assertEqual('', docker('ps', '--all', '--quiet', '--filter', f'ancestor={image}'))
            finally:
                if built:
                    docker('image', 'rm', '--force', image)

    def refused(self, image):
        result = execute(image)
        self.assertEqual(2, result.returncode)
        self.assertNotIn('accepted', result.stdout)
        self.assertNotIn('Traceback', result.stderr)
        self.assertNotIn('synthetic', result.stderr)

    def test_complete_actual_image_accepts_manifest_fonts_and_revision(self):
        def accepted(image):
            result = execute(image)
            self.assertEqual(0, result.returncode, result.stderr)
            receipt = json.loads(result.stdout)
            self.assertEqual('accepted', receipt['status'])
            self.assertEqual(22, receipt['assetCount'])
            self.assertEqual(12, receipt['fontCount'])
            self.assertEqual(REVISION, receipt['sourceRevision'])
        self.with_image(accepted)

    def test_each_required_packaged_asset_missing_or_empty_refused(self):
        for asset in ASSETS + ['asset-manifest.json']:
            for empty in (False, True):
                with self.subTest(asset=asset, empty=empty):
                    self.with_image(self.refused, broken='dist/' + asset, empty=empty)

    def test_each_referenced_font_missing_or_empty_refused(self):
        for font in FONT_PATHS:
            for empty in (False, True):
                with self.subTest(font=font, empty=empty):
                    self.with_image(self.refused, broken=font, empty=empty)

    def test_manifest_omission_and_duplicate_keys_refused(self):
        missing = dict(MANIFEST, scripts=['vendor.min.js'])
        for manifest in (json.dumps(missing), json.dumps(MANIFEST)[:-1] + ',"scripts":[]}'):
            with self.subTest(manifest=manifest[:20]):
                self.with_image(self.refused, manifest=manifest)

    def test_missing_mismatched_and_abbreviated_revision_labels_refused(self):
        for label in (None, 'b' * 40, REVISION[:7]):
            with self.subTest(label=label):
                self.with_image(self.refused, label=label)

    def test_font_family_omission_and_remote_reference_refused(self):
        for css in ('body{color:black}', '@font-face{src:url(https://example.invalid/private.woff2)}',
                    '@font-face{src:url(./assets/../private.woff2)}'):
            with self.subTest(css=css):
                self.with_image(self.refused, css=css)

    def test_unavailable_image_fails_closed(self):
        self.refused('sha256:' + '0' * 64)

    def test_invalid_expected_revision_and_unknown_dockerfile_refused(self):
        for revision in ('', 'A' * 40, REVISION[:7]):
            self.assertEqual(2, execute('sha256:' + '0' * 64, revision=revision).returncode)
        self.assertEqual(2, execute('sha256:' + '0' * 64, dockerfile='other/Dockerfile').returncode)

    def test_other_service_does_not_acquire_web_requirement(self):
        result = execute('sha256:' + '0' * 64, repository='MALIEV-Co-Ltd/Legacy.Maliev.FileService')
        self.assertEqual(0, result.returncode)
        self.assertEqual({'status': 'not-applicable'}, json.loads(result.stdout))

    def test_actual_workflow_labels_build_and_checks_before_scanning_publication(self):
        workflow = (ROOT / '.github/workflows/publish-image.yml').read_text()
        self.assertIn('labels: org.opencontainers.image.revision=${{ github.sha }}', workflow)
        build = workflow.index('      - name: Build image once for scanning and publication\n')
        gate = workflow.index('      - name: Verify packaged Web assets and source revision\n')
        scan = workflow.index('      - name: Scan the built image before publication\n')
        publish = workflow.index('      - name: Publish and resolve immutable digest\n')
        self.assertLess(build, gate)
        self.assertLess(gate, scan)
        self.assertLess(scan, publish)
        gate_header = workflow[gate:workflow.index('        run: |\n', gate)]
        self.assertNotIn('continue-on-error', gate_header)
        self.assertNotIn('        if:', gate_header)
        self.assertIn('EXPECTED_SOURCE_REVISION: ${{ github.sha }}', gate_header)


if __name__ == '__main__':
    unittest.main(verbosity=2)
