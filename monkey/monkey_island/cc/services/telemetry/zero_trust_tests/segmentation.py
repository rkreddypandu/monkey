import itertools
from six import text_type

from common.data.zero_trust_consts import STATUS_CONCLUSIVE, EVENT_TYPE_MONKEY_NETWORK
from common.network.network_range import NetworkRange
from common.network.segmentation_utils import get_ip_in_src_and_not_in_dst, get_ip_if_in_subnet
from monkey_island.cc.models import Monkey
from monkey_island.cc.models.zero_trust.event import Event
from monkey_island.cc.models.zero_trust.segmentation_finding import SegmentationFinding
from monkey_island.cc.services.configuration.utils import get_config_network_segments_as_subnet_groups

SEGMENTATION_VIOLATION_EVENT_TEXT = \
    "Segmentation violation! Monkey on '{hostname}', with the {source_ip} IP address (in segment {source_seg}) " \
    "managed to communicate cross segment to {target_ip} (in segment {target_seg})."


def is_segmentation_violation(current_monkey, target_ip, source_subnet, target_subnet):
    if source_subnet == target_subnet:
        return False
    source_subnet_range = NetworkRange.get_range_obj(source_subnet)
    target_subnet_range = NetworkRange.get_range_obj(target_subnet)

    if target_subnet_range.is_in_range(text_type(target_ip)):
        cross_segment_ip = get_ip_in_src_and_not_in_dst(
            current_monkey.ip_addresses,
            source_subnet_range,
            target_subnet_range)

        return cross_segment_ip is not None


def test_segmentation_violation(telemetry_json):
    """

    :param telemetry_json: A SCAN telemetry sent from a Monkey.
    """
    # TODO - lower code duplication between this and report.py.
    # TODO - single machine
    current_monkey = Monkey.get_single_monkey_by_guid(telemetry_json['monkey_guid'])
    target_ip = telemetry_json['data']['machine']['ip_addr']
    subnet_groups = get_config_network_segments_as_subnet_groups()
    for subnet_group in subnet_groups:
        subnet_pairs = itertools.product(subnet_group, subnet_group)
        for subnet_pair in subnet_pairs:
            source_subnet = subnet_pair[0]
            target_subnet = subnet_pair[1]
            if is_segmentation_violation(current_monkey, target_ip, source_subnet, target_subnet):
                event = get_segmentation_violation_event(current_monkey, source_subnet, target_ip, target_subnet)
                SegmentationFinding.create_or_add_to_existing_finding(
                    subnets=[source_subnet, target_subnet],
                    status=STATUS_CONCLUSIVE,
                    segmentation_event=event
                )


def get_segmentation_violation_event(current_monkey, source_subnet, target_ip, target_subnet):
    return Event.create_event(
        title="Segmentation event",
        message=SEGMENTATION_VIOLATION_EVENT_TEXT.format(
            hostname=current_monkey.hostname,
            source_ip=get_ip_if_in_subnet(current_monkey.ip_addresses, NetworkRange.get_range_obj(source_subnet)),
            source_seg=source_subnet,
            target_ip=target_ip,
            target_seg=target_subnet
        ),
        event_type=EVENT_TYPE_MONKEY_NETWORK
    )


def test_positive_findings_for_unreached_segments(telemetry_json):
    current_monkey = Monkey.get_single_monkey_by_guid(telemetry_json['monkey_guid'])
    subnet_groups = get_config_network_segments_as_subnet_groups()