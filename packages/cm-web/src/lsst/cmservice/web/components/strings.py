NODE_RECOVERY_DIALOG_LABEL = """Recover a failed node"""

NODE_RESTART_TOOLTIP = """Attempt a BPS Restart of a Failed Group"""
NODE_RETRY_TOOLTIP = """Attempt a new BPS Submit of a Failed Group"""
NODE_RESET_TOOLTIP = """Completely reset the Node to the beginning"""
NODE_FORCE_TOOLTIP = """Unconditionally accept the Node irrespective of its failure"""
NODE_RESCUE_TOOLTIP = """Accept this Group and create a new Rescue Group in the graph"""

LIBRARY_MANIFEST_TOOLIP = (
    """Library manifests are read-only global configuration documents that provide defaults for campaigns"""
)
CAMPAIGN_MANIFEST_TOOLTIP = """Campaign manifests are versioned configuration documents for a campaign"""
BREAKPOINT_ACCEPT_TOOLTIP = """Accept the campaign at the breakpoint and continue processing"""
BREAKPOINT_REJECT_TOOLTIP = """Reject the campaign at the breakpoint and stop processing"""

NODE_RESTART_CONFIRMATION_DETAIL = """\
    This action will attempt a BPS restart operation on the failed node.
    This will not change the configuration used by the attempt. This action is only available when a BPS
    submit directory and QGraph file is available.
    """
NODE_RETRY_CONFIRMATION_DETAIL = """\
    This action will attempt to execute the node's payload without making any changes to the configuration
    or prepared artifacts.
    """
NODE_RESET_CONFIRMATION_DETAIL = """\
    This action is "nuclear" -- all generated configuration and artifacts for the failed Node are removed, and
    the state set back to a clean beginning. This does not determine or verify whether any data products or
    collections were created, nor does it attempt to delete any data products or collections.
    """
NODE_RESCUE_CONFIRMATION_DETAIL = """\
    This action will try to rescue a failed group by creating a clone of this group in the campaign graph.
    The clone copy will use a new output and run collection, and its BPS configuration will be
    set to "skip-existing-in" this failed group's run collection.
    The failed group will be forced into an accepted state, ignoring any error conditions. If you want to
    exclude the failed group's run collection from future collection chains, you must manually "reject" the
    group. After a rescue, the campaign will remain in a paused state to allow you time to edit the clone
    rescue group's configuration.
    """
NODE_FORCE_CONFIRMATION_DETAIL = """\
    This action will ignore any failure states and mark the node as "accepted".
    If this node is a Group, any partial outputs in its run collection will be included in the step output.
    If no run collection exists, this can cause an error later when creating collection chains.
    """

GROUP_TOGGLE_REJECT_DETAIL = """\
    Rejecting a Group means that for campaign evolution purposes, the
    group is "successful" but its run collection will be excluded from
    any step outputs.

    Are you sure you want to reject this Group?
    """
GROUP_TOGGLE_ACCEPT_DETAIL = """\
    Accepting a Group means that irrespective of any failures or
    partial results, the Group's run collection will be included with
    any step outputs.

    Are you sure you want to accept this Group?
"""
