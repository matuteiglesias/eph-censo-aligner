import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from aligner.release import RegistryError, create_release, load_registry, validate_registry
from aligner.integration import CompatibilityError, validate_release

ROOT = Path(__file__).parents[1]

def digest_tree(path):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir()}

def test_fixture_release_is_deterministic(tmp_path):
    kwargs = dict(input_path=ROOT/'fixtures/eph/hogar.csv', direction='eph-to-censo', entity='hogar', source_vintage='fixture-v1', region_path=ROOT/'fixtures/regions.csv', release_id='fixture-v1')
    create_release(output_dir=tmp_path/'a', **kwargs)
    create_release(output_dir=tmp_path/'b', **kwargs)
    assert digest_tree(tmp_path/'a') == digest_tree(tmp_path/'b')
    out = pd.read_csv(tmp_path/'a/aligned.csv')
    assert out.record_id.tolist() == ['r1', 'r2']
    assert out.columns.tolist()[:6] == ['CODUSU','NRO_HOGAR','ANO4','TRIMESTRE','record_id','AGLOMERADO']
    loss = json.loads((tmp_path/'a/loss-report.json').read_text())
    assert loss['records_removed_or_invalidated'] == 1
    assert loss['ambiguous_rules']
    assert loss['terminal_dispositions'] == {
        'emitted': 2, 'failed': 0, 'invalid': 0, 'removed': 1,
        'unmatched': 0, 'unsupported': 0,
    }
    assert loss['reconciliation']['reconciled'] is True
    assert loss['reconciliation']['difference'] == 0

def test_reverse_release_and_geography_override(tmp_path):
    create_release(ROOT/'fixtures/censo/hogar.csv', tmp_path, 'censo-to-eph', 'hogar', 'fixture-v1', ROOT/'fixtures/regions.csv')
    out = pd.read_csv(tmp_path/'aligned.csv')
    assert out.Region.tolist() == ['Gran Buenos Aires', 'Patagónica']
    assert out.IV4.tolist() == [2, 9]

def test_unknown_vintage_stops(tmp_path):
    with pytest.raises(ValueError, match='Unsupported vintage'):
        create_release(ROOT/'fixtures/censo/hogar.csv', tmp_path, 'censo-to-eph', 'hogar', '2022')

def test_reverse_rule_is_independent_not_forward_inversion(tmp_path):
    """Forward IV10 category 3 collapses to 2; reverse H11=2 stays 2."""
    forward = pd.DataFrame([{
        'IX_TOT': 1, 'CH04': 1, 'CH06': 30, 'CONDACT': 1,
        'AGLOMERADO': 1, 'IV1': 1, 'IV10': 3,
    }])
    reverse = pd.DataFrame([{
        'IX_TOT': 1, 'P02': 1, 'P03': 30, 'CONDACT': 1,
        'AGLOMERADO': 1, 'H11': 2,
    }])
    forward.to_csv(tmp_path/'forward.csv', index=False)
    reverse.to_csv(tmp_path/'reverse.csv', index=False)
    create_release(tmp_path/'forward.csv', tmp_path/'f', 'eph-to-censo', 'hogar', 'fixture-v1')
    create_release(tmp_path/'reverse.csv', tmp_path/'r', 'censo-to-eph', 'hogar', 'fixture-v1')
    assert pd.read_csv(tmp_path/'f/aligned.csv').H11.tolist() == [2]
    assert pd.read_csv(tmp_path/'r/aligned.csv').IV10.tolist() == [2]

def test_registry_rejects_equal_precedence_and_implicit_composition():
    registry = load_registry()
    duplicate = dict(registry['mappings'][0], mapping_id='duplicate')
    registry['mappings'].append(duplicate)
    with pytest.raises(RegistryError, match='Equal-precedence'):
        validate_registry(registry)

    registry = load_registry()
    original = registry['mappings'][0]
    competing = dict(
        original, mapping_id='competing', target_variable='OTHER',
        rule_priority=original['rule_priority'] + 1,
    )
    registry['mappings'].append(competing)
    with pytest.raises(RegistryError, match='unambiguous composition'):
        validate_registry(registry)

def test_shared_artifact_envelope_and_consumer_validation(tmp_path):
    create_release(
        ROOT/'fixtures/censo/hogar.csv', tmp_path/'release', 'censo-to-eph',
        'hogar', 'fixture-v1', ROOT/'fixtures/regions.csv', release_id='crosswalk-fixture-v1',
    )
    manifest_path = tmp_path/'release/manifest.json'
    manifest = validate_release(
        manifest_path, expected_vintage='fixture-v1',
        geography_identifier_contract='research.argentina-dpto/v1',
    )
    assert manifest['manifest_schema'] == 'research-artifact-manifest/v1'
    assert manifest['artifact_type'] == 'research.eph-census-crosswalk'
    assert manifest['status'] == 'synthetic'
    assert set(manifest['producer']) == {'repository', 'commit', 'dirty_worktree'}
    assert {entry['role'] for entry in manifest['files']} == {
        'aligned-data', 'variable-mapping-report',
        'loss-and-ambiguity-report', 'compatibility-declaration',
    }
    assert {entry['role'] for entry in manifest['reports']} == {
        'variable-mapping-report', 'loss-and-ambiguity-report',
    }

    with pytest.raises(CompatibilityError, match='synthetic crosswalk'):
        validate_release(manifest_path, requested_mode='real')
    with pytest.raises(CompatibilityError, match='approved methodological'):
        validate_release(manifest_path, requested_mode='approved')
    with pytest.raises(CompatibilityError, match='Unsupported source vintage'):
        validate_release(manifest_path, expected_vintage='2024-Q3')
    with pytest.raises(CompatibilityError, match='geography identifier'):
        validate_release(manifest_path, geography_identifier_contract='other/v1')
    with pytest.raises(CompatibilityError, match='Manifest checksum mismatch'):
        validate_release(manifest_path, expected_manifest_sha256='0' * 64)
    with pytest.raises(CompatibilityError, match='Input manifest checksum mismatch'):
        validate_release(
            manifest_path,
            expected_input_manifests={'source-data': '1' * 64},
        )

    too_new = dict(manifest, manifest_schema='research-artifact-manifest/v2')
    newer_path = tmp_path/'release/newer-manifest.json'
    newer_path.write_text(json.dumps(too_new), encoding='utf-8')
    with pytest.raises(CompatibilityError, match='Unsupported manifest schema'):
        validate_release(newer_path)

def test_consumer_rejects_tampered_artifact(tmp_path):
    create_release(
        ROOT/'fixtures/eph/hogar.csv', tmp_path, 'eph-to-censo',
        'hogar', 'fixture-v1', ROOT/'fixtures/regions.csv',
    )
    (tmp_path/'aligned.csv').write_text('tampered\n', encoding='utf-8')
    with pytest.raises(CompatibilityError, match='checksum mismatch'):
        validate_release(tmp_path/'manifest.json')
