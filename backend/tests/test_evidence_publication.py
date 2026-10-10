"""Regression: absent data must never become an adverse company finding."""
import asyncio
from services.evidence import CompanyIdentity, unavailable_signal
from services.scorer import compute_score
from services.reports import build_company_report
from services.collectors import CollectorResult
from services.resolver import ResolvedCompany


def test_deloitte_news_only_is_unrated_in_score_and_report():
    signals = [{'signal': name, 'raw_score': None, 'availability_status': 'unavailable'} for name in (
        'Commercial Credit Risk', 'B2B Payment Behavior', 'Cash Flow & Liquidity',
        'Business Identity & Standing', 'Liens, Bankruptcy & Litigation',
        'Brand Legitimacy & Web Presence', 'Company Stability', 'Job Posting Velocity')]
    signals.append({'signal': 'News & Media Sentiment', 'raw_score': 65,
                    'availability_status': 'live', 'evidence_quality': 'low', 'category': 'sentiment'})
    result = compute_score(signals, resolution_confidence=10)
    assert result['private_score'] is None
    assert result['rating'] == 'Insufficient public evidence'
    assert result['meta']['confidence'] < .03
    report = build_company_report({**result, 'company_name': 'Deloitte'})
    assert report['risk_level'] == 'Unrated'
    assert report['score'] is None
    assert 'distressed' not in report['headline'].lower()


def test_missing_causes_are_distinct_and_do_not_manufacture_scores(monkeypatch):
    from services import reports
    async def resolve(*args, **kwargs):
        return ResolvedCompany(query_name='Example', canonical_key='example', canonical_name='Example', legal_name='Example')
    def absent(name):
        return {'signal': name, 'raw_score': None, 'availability_status': 'unavailable'}
    async def collect(*args, **kwargs):
        return {'signals': [unavailable_signal('Commercial Credit Risk'), absent('Industry Context'),
                            absent('Brand Legitimacy & Web Presence'), absent('Company Stability')],
                'evidence': {}, 'collector_results': [
                    CollectorResult(source='census', status='unavailable', error_code='NOT_CONFIGURED'),
                    CollectorResult(source='wikipedia', status='unavailable', error_code='TIMEOUT'),
                ]}
    monkeypatch.setattr(reports, 'resolve_company', resolve)
    monkeypatch.setattr(reports, 'collect_all', collect)
    monkeypatch.setattr(reports, 'licensed_data_enabled', lambda: False)
    result = asyncio.run(reports.score_company('Example', identity=CompanyIdentity(legal_name='Example'), refresh=True))
    assert result['dataCoverage']['availabilityReasons'] == {'not_connected': 2, 'lookup_failed': 2, 'no_verified_match': 0}
    assert result['private_score'] is None
    assert all(row['raw_score'] is None for row in result['breakdown'])
