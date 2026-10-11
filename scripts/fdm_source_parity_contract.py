"""Source-obligation mapping only; never certifies runtime, coverage or activation."""
import argparse
import json
from pathlib import PurePosixPath
import re
import sys

SOURCE = '29214f53f1574b89799e6d58ea1cebea03fffe04'
PARENT = '135e526d0dab85c415b3afdcefd7b70fe2c82e2f'
BASELINE = 'f29f2ce40bf31b067e84b6de4e3547d2fe2c3de3'
READINESS_PATHS = (
    'Maliev.Web.Tests/FreshHostStartupTests.cs',
    'Maliev.Web.Tests/InstantQuotationAuthenticatedProfilePageTests.cs',
    'Maliev.Web.Tests/InstantQuotationBrowserFixture.cs',
    'Maliev.Web.Tests/InstantQuotationGeometryAnalysisBrowserTests.cs',
    'Maliev.Web.Tests/InstantQuotationLayoutGeometryTests.cs',
    'Maliev.Web.Tests/InstantQuotationPreliminaryQuotationBrowserTests.cs',
    'Maliev.Web.Tests/InstantQuotationScrollAffordanceTests.cs',
    'Maliev.Web.Tests/JavaScript/material-selection-scroll.test.cjs',
    'Maliev.Web.Tests/MeasurementTrackingSourceTests.cs',
    'Maliev.Web.Tests/NativeLoggingMigrationTests.cs',
    'Maliev.Web.Tests/SecurityHeaderPolicySourceTests.cs',
    'Maliev.Web.Tests/SharedFrontendBundleSourceTests.cs',
    'Maliev.Web/Pages/InstantQuotation/3D-Printing.cshtml',
    'Maliev.Web/wwwroot/src/app/js/model-viewer/model-viewer.js',
)
PRICING_PATHS = (
    'Maliev.Web/Pricing/PricingCatalog.cs',
    'Maliev.Web/Pricing/PricingEngine.cs',
    'Maliev.Web.Tests/AdditiveQuoteTicketServiceTests.cs',
    'Maliev.Web.Tests/FdmQuantityMarginTests.cs',
    'Maliev.Web.Tests/FdmQuantityPricingBrowserTests.cs',
    'Maliev.Web.Tests/FdmQuantityPricingEndpointTests.cs',
)
PATHS = PRICING_PATHS + READINESS_PATHS
JOURNALS = (
    ('Maliev.Web.Tests/FdmQuantityPricingBrowserTests.cs',49,'fdm_initial_price_wait_start','fixed'),
    ('Maliev.Web.Tests/FdmQuantityPricingBrowserTests.cs',59,'fdm_initial_price_wait_complete','fixed'),
    ('Maliev.Web.Tests/FdmQuantityPricingBrowserTests.cs',63,'fdm_physical_preparation_start','fixed'),
    ('Maliev.Web.Tests/FdmQuantityPricingBrowserTests.cs',73,'fdm_physical_preparation_complete','fixed'),
    ('Maliev.Web.Tests/FdmQuantityPricingBrowserTests.cs',104,'fdm_quote_request_start','fixed'),
    ('Maliev.Web.Tests/FdmQuantityPricingBrowserTests.cs',121,'fdm_quote_request_complete','fixed'),
    ('Maliev.Web.Tests/InstantQuotationBrowserFixture.cs',272,'loaded_setup_start','fixed'),
    ('Maliev.Web.Tests/InstantQuotationBrowserFixture.cs',277,'failed_setup_cleanup_start','fixed'),
    ('Maliev.Web.Tests/InstantQuotationBrowserFixture.cs',282,'failed_setup_cleanup_complete','fixed'),
    ('Maliev.Web.Tests/InstantQuotationBrowserFixture.cs',287,'failed_setup_cleanup_failed','fixed'),
    ('Maliev.Web.Tests/InstantQuotationBrowserFixture.cs',312,'http_','dynamic-prefix'),
    ('Maliev.Web.Tests/InstantQuotationBrowserFixture.cs',368,'loaded_upload_start','fixed'),
    ('Maliev.Web.Tests/InstantQuotationBrowserFixture.cs',454,'part_pipeline_wait_start','fixed'),
    ('Maliev.Web.Tests/InstantQuotationBrowserFixture.cs',463,'part_pipeline_wait_complete','fixed'),
    ('Maliev.Web.Tests/InstantQuotationBrowserFixture.cs',464,'part_price_wait_start','fixed'),
    ('Maliev.Web.Tests/InstantQuotationBrowserFixture.cs',476,'part_price_wait_complete','fixed'),
    ('Maliev.Web.Tests/InstantQuotationPreliminaryQuotationBrowserTests.cs',33,'pdf_case_start','fixed'),
    ('Maliev.Web.Tests/InstantQuotationPreliminaryQuotationBrowserTests.cs',191,'pdf_render_start','fixed'),
    ('Maliev.Web.Tests/InstantQuotationPreliminaryQuotationBrowserTests.cs',193,'pdf_render_complete','fixed'),
)
BEHAVIORS = (
    ('margin','FdmQuantityMarginTests'),
    ('endpoint','FdmQuantityPricingEndpointTests'),
    ('ticket','AdditiveQuoteTicketServiceTests'),
    ('persistence','OnPostSubmitRequestAsync_QuantityMarginPriceSurvivesRequestPersistence'),
    ('startup','FreshHostStartupTests'),
    ('browser','FdmQuantityPricingBrowserTests'),
    ('readiness-summary','LoadedConfigurator_KeepsSummaryInViewport_AndScrollsOnlyMaterials'),
    ('readiness-pdf','PreliminaryQuotationPreview_RendersAllPartsAndA4Pdf'),
    ('readiness-worker','ModelWorkerUrl_IsVersionedPerBuild'),
    ('readiness-collapsed-summary','ConfigurationSummary_StartsCollapsed_AndExpandsWithoutChangingTotal'),
    ('readiness-material-filter','MaterialCards_KeepTheirSize_WhenSearchFiltersTheCatalogue'),
    ('readiness-bulk-table','BulkPricingTable_AcceptsTenThousandUnits_AndOmitsRepeatedTerminalPrices'),
    ('readiness-selected-material','ChoosingAMaterial_KeepsTheChosenCardInView'),
    ('readiness-seven-part','SevenPartBatch_ReturnsNonzeroProtectedOrderTotal'),
)


class ContractError(ValueError):
    pass


def require(condition):
    if not condition:
        raise ContractError('FDM source parity contract rejected')


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected))


def sha(value, size):
    require(type(value) is str and re.fullmatch('[0-9a-f]{'+str(size)+'}',value) is not None)


def path(value):
    require(type(value) is str and 0 < len(value) <= 512 and '\\' not in value and ':' not in value)
    p = PurePosixPath(value)
    require(not p.is_absolute() and all(part not in ('','.','..') for part in value.split('/')))
    require(value.startswith(('Legacy.Maliev.Web/','Legacy.Maliev.Web.Tests/','Legacy.Maliev.Web.Application/','tests/','scripts/')))


def validate(document, expected_head, expected_full_recipe):
    sha(expected_head,40); sha(expected_full_recipe,40)
    require(expected_head != BASELINE and expected_full_recipe != BASELINE)
    keys(document,('schema','sourceSha','sourceParent','candidateHead','fullRecipeHead','sourcePaths','journals','behaviors','startup','candidateHeadInterface'))
    require(document['schema']=='fdm-source-parity/v1' and document['sourceSha']==SOURCE and document['sourceParent']==PARENT)
    require(document['candidateHead']==expected_head and document['fullRecipeHead']==expected_full_recipe)
    keys(document['candidateHeadInterface'],('name','required','callerPassesExactHead','calleeChecksActualHead'))
    interface=document['candidateHeadInterface']
    require(interface['name']=='candidate_head' and interface['required'] is True and interface['callerPassesExactHead'] is True and interface['calleeChecksActualHead'] is True)
    paths=document['sourcePaths']; require(type(paths) is list and len(paths)==len(PATHS))
    seen=set();admitted={};source_targets={}
    for row in paths:
        keys(row,('sourcePath','targetFiles'))
        require(row['sourcePath'] in PATHS and row['sourcePath'] not in seen);seen.add(row['sourcePath'])
        require(type(row['targetFiles']) is list and 0 < len(row['targetFiles']) <= 32)
        targets=set()
        for target in row['targetFiles']:
            keys(target,('path','bytes','sha256'));path(target['path']);sha(target['sha256'],64)
            require(type(target['bytes']) is int and 0 < target['bytes'] <= 4*1024**2 and target['path'] not in targets);targets.add(target['path'])
            pin=(target['bytes'],target['sha256'])
            require(target['path'] not in admitted or admitted[target['path']]==pin);admitted[target['path']]=pin
        source_targets[row['sourcePath']]=targets
    require(seen==set(PATHS))
    journals=document['journals'];require(type(journals) is list and len(journals)==len(JOURNALS));seen=set()
    for row in journals:
        keys(row,('sourcePath','sourceLine','name','kind','targetPath','targetPhase','scenario'))
        identity=(row['sourcePath'],row['sourceLine'],row['name'],row['kind'])
        require(type(row['sourceLine']) is int and identity in JOURNALS and identity not in seen);seen.add(identity);path(row['targetPath'])
        require(row['targetPath'] in source_targets[row['sourcePath']])
        require(row['targetPhase']==row['name'])
        require(row['scenario']==('setup-failure' if row['name'].startswith('failed_setup_cleanup_') else 'normal'))
    require(seen==set(JOURNALS))
    behaviors=document['behaviors'];require(type(behaviors) is list and len(behaviors)==len(BEHAVIORS));seen=set();filters=set();common_rows=None
    for row in behaviors:
        keys(row,('id','sourceSelector','targetFilter','expectedPassingRows'))
        identity=(row['id'],row['sourceSelector']);require(identity in BEHAVIORS and identity not in seen);seen.add(identity)
        require(type(row['targetFilter']) is str and 0 < len(row['targetFilter']) <= 4096 and all(32 <= ord(c) < 127 for c in row['targetFilter']))
        filters.add(row['targetFilter'])
        rows=row['expectedPassingRows'];require(type(rows) is list and 0 < len(rows) <= 4096);identities=set()
        for result in rows:
            keys(result,('class','method','displaySha256'));sha(result['displaySha256'],64)
            require(type(result['class']) is str and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*(?:[.+][A-Za-z_][A-Za-z_0-9]*)*',result['class']))
            require(type(result['method']) is str and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',result['method']))
            row_identity=(result['class'],result['method'],result['displaySha256']);require(row_identity not in identities);identities.add(row_identity)
        common_rows=identities if common_rows is None else common_rows & identities
    require(seen==set(BEHAVIORS))
    # The original selectors span startup, pricing and eight separate readiness
    # behaviors. One generic filter/case for every group is not that mapping.
    # Partial row/filter overlap remains permitted; no disjointness is inferred.
    require(len(filters)>1 and not common_rows)
    keys(document['startup'],('environment','expectedHead','proofPath','liveness','quotation','finallyCleanup'))
    startup=document['startup'];path(startup['proofPath'])
    require(startup['environment']=='Development' and startup['expectedHead']==expected_head)
    require(all(startup[key] is True for key in ('liveness','quotation','finallyCleanup')))
    return dict(sourcePaths=20,source551Paths=6,source552Paths=14,fixedJournalObligations=18,dynamicJournalPrefixes=1,behaviorExecutionGroups=14,
                candidateHead=expected_head,sourceContractValidated=True,runtimeAcceptance=False,activationPermitted=False)


def pairs(items):
    result={}
    for key,value in items:
        require(key not in result);result[key]=value
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True);parser.add_argument('--candidate-head',required=True);parser.add_argument('--full-recipe-head',required=True)
    args=parser.parse_args(argv)
    try:
        from pathlib import Path
        raw=Path(args.manifest).read_bytes();require(len(raw)<=1024**2)
        result=validate(json.loads(raw.decode('utf-8'),object_pairs_hook=pairs),args.candidate_head,args.full_recipe_head)
        print(json.dumps(result,sort_keys=True));return 0
    except (ContractError,OSError,UnicodeError,json.JSONDecodeError,TypeError):
        print('FDM source parity contract rejected; details withheld',file=sys.stderr);return 2


if __name__=='__main__':
    raise SystemExit(main())
