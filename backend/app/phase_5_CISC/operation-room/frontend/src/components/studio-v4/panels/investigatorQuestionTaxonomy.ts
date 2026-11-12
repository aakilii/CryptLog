export type InvestigatorQuestionSpec = {
    questionType: string
    panel: string
    visualPattern: string
    drillPath: string[]
}

export const INVESTIGATOR_QUESTION_TAXONOMY: InvestigatorQuestionSpec[] = [
    {
        questionType: 'case_context_confidence',
        panel: 'TimelinePanel',
        visualPattern: 'intake_summary_plus_scope_confidence',
        drillPath: ['summary_metric', 'source_module', 'evidence_key'],
    },
    {
        questionType: 'plan_accountability',
        panel: 'TimelinePanel',
        visualPattern: 'phase_board_with_approval_checkpoints',
        drillPath: ['phase_checkpoint', 'approval_record', 'evidence_key'],
    },
    {
        questionType: 'run_transparency',
        panel: 'TimelinePanel',
        visualPattern: 'live_phase_timeline_plus_module_state_lanes',
        drillPath: ['phase_event', 'module_state', 'evidence_key'],
    },
    {
        questionType: 'timeline_reconstruction',
        panel: 'TimelinePanel',
        visualPattern: 'layered_timeline_events_severity_actor_bands',
        drillPath: ['timeline_event', 'source_record', 'evidence_key'],
    },
    {
        questionType: 'actor_behavior',
        panel: 'CorrelationPanel',
        visualPattern: 'ranked_actor_bars_plus_sequence_table',
        drillPath: ['actor_bucket', 'event_sequence', 'evidence_key'],
    },
    {
        questionType: 'anomaly_explainability',
        panel: 'AnomalyPanel',
        visualPattern: 'shap_feature_bars_plus_event_explanations',
        drillPath: ['anomaly_finding', 'model_features', 'evidence_key'],
    },
    {
        questionType: 'network_exfil_suspicion',
        panel: 'NetworkPanel',
        visualPattern: 'top_flows_table_plus_directional_flow_map',
        drillPath: ['network_flow', 'packet_summary', 'evidence_key'],
    },
    {
        questionType: 'data_access_abuse',
        panel: 'CRUDPanel',
        visualPattern: 'crud_matrix_actor_x_data_class',
        drillPath: ['crud_bucket', 'actor_action', 'evidence_key'],
    },
    {
        questionType: 'admissibility_readiness',
        panel: 'VaultPanel',
        visualPattern: 'gate_checklist_with_blockers_and_severity',
        drillPath: ['gate_check', 'blocking_condition', 'evidence_key'],
    },
    {
        questionType: 'report_confidence_rollup',
        panel: 'VaultPanel',
        visualPattern: 'section_confidence_rollup_with_drilldown',
        drillPath: ['report_section', 'confidence_factor', 'evidence_key'],
    },
    {
        questionType: 'impact_depth',
        panel: 'DepthPanel',
        visualPattern: 'depth_score_bars',
        drillPath: ['impact_dimension', 'supporting_finding', 'evidence_key'],
    },
    {
        questionType: 'evidence_provenance',
        panel: 'VaultPanel',
        visualPattern: 'evidence_reference_table',
        drillPath: ['evidence_key', 'vault_reference', 'source_module'],
    },
]

export const getQuestionSpec = (questionType: string): InvestigatorQuestionSpec | undefined => {
    return INVESTIGATOR_QUESTION_TAXONOMY.find((spec) => spec.questionType === questionType)
}
