# Legacy Helper Public-Beta Deprecation Notice

Status: notice started; deprecation cycle **not complete**.

This notice begins the mandatory public-beta deprecation cycle for the legacy
helper collection tracked by issues #73 and #62.

## Notice window

- Start event: Phase 2A merge
- Notice start: `2026-07-23T00:40:54Z`
- 90-day threshold: `2026-10-21T00:40:54Z`
- Required cycle: at least one documented public-beta deprecation cycle
- Eligibility rule: whichever occurs later—the 90-day minimum or completion of
  the required public-beta cycle

The cycle starts with this notice. It is not complete in this change. Reaching
the time threshold does not authorize Phase 2B. Phase 2B remains separately
owner-gated through issue #62 after every compatibility-window condition is
satisfied.

## Current compatibility status

All **154 tracked helper Python modules remain included in the wheel today**.
No helper has been removed, moved, renamed, or behaviorally changed by this
notice.

Seven modules have temporary import and registry compatibility:

1. `zscripts.helpers.numpy.array_utils`
2. `zscripts.helpers.pandas.concat_csvs`
3. `zscripts.helpers.pandas.excel_to_json_posts`
4. `zscripts.helpers.pillow.add_watermark`
5. `zscripts.helpers.pillow.ratio_image_2`
6. `zscripts.helpers.requests.http`
7. `zscripts.helpers.web_crawl.html_ops`

Their exact callable and registry surfaces are documented in the
[`Phase 2A compatibility contract`](LEGACY_HELPER_COMPATIBILITY.md), and their
consumer evidence is documented in the
[`consumer and ownership review`](LEGACY_HELPER_CONSUMER_REVIEW.md).

All other helpers are legacy, unsupported, and temporarily wheel-included.
Temporary compatibility does not declare any helper safe for unreviewed input,
production-supported, or behaviorally stable.

## Release and versioning expectations

Zscripts is in public beta. No stable release or semantic-version compatibility
guarantee exists for the helper collection. The compatibility window is a
public-source deprecation commitment, not a stable API or support contract.

This notice does not:

- begin Phase 2B;
- remove helpers from the wheel;
- change package discovery, dependencies, registry targets, or Torch versions;
- add an executing compatibility shim;
- create an extraction repository or package; or
- publish a package, tag, or GitHub Release.

## Feedback and security reporting

Share non-sensitive compatibility evidence, migration needs, or consumer
feedback through
[`GitHub issues`](https://github.com/Nobodyworld/dev-logger-zscripts/issues) or
GitHub Discussions when Discussions are enabled.
Do not post credentials, private source, personal data, proprietary paths, or
other sensitive material.

Potential vulnerabilities must follow
[`SECURITY.md`](../../SECURITY.md), not a public issue or Discussion.
