"""Convert BGP observation evidence into AS prefix records."""

from collections.abc import Iterable
from ipaddress import IPv4Network

from netvoyager_core.logging import get_logger
from netvoyager_network.bgp.models import AsPrefix

from ..evidence.models import EvidenceRecord
from .exceptions import InvalidBgpEvidenceError
from .models import AsPrefixConversionResult, EvidencedAsPrefix


logger = get_logger("analysis.bgp.conversion")


def _convert_observation(evidence: EvidenceRecord) -> AsPrefix | None:
    """Validate one BGP observation and convert its known origin.

    Require one canonical IPv4 prefix subject and explicit origin/path
    details. A known origin must agree across the ASN subject, origin_asn
    detail, and last AS-path element.

    Return None only for a valid observation with an empty or unavailable
    path, no ASN subject, and no attributed origin or attribution method.

    Validate the fields needed for conversion. Unrelated evidence details
    and source metadata are not validated here.
    """
    if evidence.kind != "bgp.prefix_observed":
        raise InvalidBgpEvidenceError(
            evidence_id=evidence.evidence_id,
            reason="Expected evidence kind 'bgp.prefix_observed'.",
        )

    prefix_subjects = [
        subject for subject in evidence.subjects
        if subject.kind == "prefix"
    ]
    asn_subjects = [
        subject for subject in evidence.subjects
        if subject.kind == "asn"
    ]

    if len(prefix_subjects) != 1:
        raise InvalidBgpEvidenceError(
            evidence_id=evidence.evidence_id,
            reason="Expected exactly one prefix subject.",
        )

    prefix_text = prefix_subjects[0].identifier

    if not isinstance(prefix_text, str):
        raise InvalidBgpEvidenceError(
            evidence_id=evidence.evidence_id,
            reason="Prefix identifier must be a canonical IPv4 CIDR string.",
        )

    try:
        prefix = IPv4Network(prefix_text, strict=True)
    except ValueError as exc:
        raise InvalidBgpEvidenceError(
            evidence_id=evidence.evidence_id,
            reason="Prefix identifier is not a valid IPv4 network.",
        ) from exc

    if str(prefix) != prefix_text:
        raise InvalidBgpEvidenceError(
            evidence_id=evidence.evidence_id,
            reason="Prefix identifier must use canonical IPv4 CIDR notation.",
        )

    required_details = ("as_path", "origin_asn", "origin_method")
    missing = [
        key for key in required_details
        if key not in evidence.details
    ]

    if missing:
        raise InvalidBgpEvidenceError(
            evidence_id=evidence.evidence_id,
            reason=f"Missing required details: {', '.join(missing)}.",
        )

    raw_path = evidence.details["as_path"]
    origin_asn = evidence.details["origin_asn"]
    origin_method = evidence.details["origin_method"]

    as_path: tuple[int, ...] | None = None

    if raw_path is not None:
        if not isinstance(raw_path, list):
            raise InvalidBgpEvidenceError(
                evidence_id=evidence.evidence_id,
                reason="as_path must be a list of integer ASNs or None.",
            )

        path_values: list[int] = []

        for value in raw_path:
            if isinstance(value, bool) or not isinstance(value, int):
                raise InvalidBgpEvidenceError(
                    evidence_id=evidence.evidence_id,
                    reason="Every AS-path element must be an integer ASN.",
                )

            if not 0 <= value <= 4294967295:
                raise InvalidBgpEvidenceError(
                    evidence_id=evidence.evidence_id,
                    reason="AS-path elements must fit an unsigned 32-bit ASN.",
                )

            path_values.append(value)

        as_path = tuple(path_values)

    if not as_path:
        if (
            asn_subjects
            or origin_asn is not None
            or origin_method is not None
        ):
            raise InvalidBgpEvidenceError(
                evidence_id=evidence.evidence_id,
                reason=(
                    "An empty or unavailable AS path must not have an ASN "
                    "subject, attributed origin, or attribution method."
                ),
            )

        return None

    if isinstance(origin_asn, bool) or not isinstance(origin_asn, int):
        raise InvalidBgpEvidenceError(
            evidence_id=evidence.evidence_id,
            reason="A nonempty AS path requires an integer origin_asn.",
        )

    if origin_asn != as_path[-1]:
        raise InvalidBgpEvidenceError(
            evidence_id=evidence.evidence_id,
            reason="origin_asn does not match the last AS-path element.",
        )

    if origin_method != "last_as_path_element":
        raise InvalidBgpEvidenceError(
            evidence_id=evidence.evidence_id,
            reason="Expected origin_method 'last_as_path_element'.",
        )

    if (
        len(asn_subjects) != 1
        or asn_subjects[0].identifier != str(origin_asn)
    ):
        raise InvalidBgpEvidenceError(
            evidence_id=evidence.evidence_id,
            reason=(
                "Expected exactly one ASN subject whose decimal identifier "
                "matches origin_asn."
            ),
        )

    return AsPrefix(
        asn=origin_asn,
        prefix=prefix,
        as_path=as_path,
    )


def convert_bgp_evidence_to_as_prefixes(
    evidence: Iterable[EvidenceRecord],
) -> AsPrefixConversionResult:
    """Convert BGP evidence while retaining observation references.

    Consume the iterable once. Preserve input encounter order and duplicate
    occurrences within the converted records and unknown-origin references.

    Known-origin observations produce EvidencedAsPrefix entries. Valid
    empty-path or unavailable-path observations retain their evidence IDs
    separately without creating a placeholder ASN or AsPrefix.

    Raise InvalidBgpEvidenceError on the first incompatible or malformed
    observation. No partial result is returned. Input evidence is not
    modified, and earlier debug messages do not imply successful completion.

    The caller retains the original evidence and selects the routing
    context before conversion. This function does not combine contexts,
    group prefixes, create autonomous systems, or assign scopes.

    Debug logs describe each conversion or unknown origin and completion
    totals. Logging configuration belongs to the calling application.
    """
    logger.debug("Starting BGP evidence conversion")

    result = AsPrefixConversionResult()
    records: list[EvidencedAsPrefix] = []
    unknown_origin_ids = []
    evidence_count = 0

    for item in evidence:
        evidence_count += 1

        try:
            record = _convert_observation(item)
        except InvalidBgpEvidenceError as exc:
            logger.debug(
                "BGP evidence conversion rejected an observation",
                extra={
                    "evidence_id": str(exc.evidence_id),
                    "reason": exc.reason,
                },
            )
            raise

        if record is None:
            unknown_origin_ids.append(item.evidence_id)

            logger.debug(
                "BGP evidence retained with unknown origin",
                extra={
                    "evidence_id": str(item.evidence_id),
                    "as_path_state": (
                        "unavailable"
                        if item.details["as_path"] is None
                        else "empty"
                    ),
                },
            )
            continue

        records.append(
            EvidencedAsPrefix(
                record=record,
                evidence_id=item.evidence_id,
            )
        )

        logger.debug(
            "BGP evidence converted to AS prefix",
            extra={
                "evidence_id": str(item.evidence_id),
                "prefix": str(record.prefix),
                "asn": record.asn,
            },
        )

    result.records = tuple(records)
    result.unknown_origin_evidence_ids = tuple(unknown_origin_ids)

    logger.debug(
        "BGP evidence conversion completed",
        extra={
            "evidence_count": evidence_count,
            "converted_count": len(result.records),
            "unknown_origin_count": len(
                result.unknown_origin_evidence_ids
            ),
        },
    )

    return result