// Test only: frozen server-authored playback from actual merged tools over the offline ingested NovaPay graph double.
import { changeWithOrderedPaths } from './orderedTraceFixture';
import type { TracePlaybackData } from '../types';

const playback: TracePlaybackData = {
  "version": 1,
  "sequences": [
    {
      "id": "decision_trace/incident_to_investigation",
      "path_id": "incident_to_investigation",
      "tool": "decision_trace",
      "support_status": "supported",
      "steps": [
        {
          "number": 1,
          "sequence_id": "decision_trace/incident_to_investigation",
          "source": "incident:INC-17",
          "type": "LED_TO",
          "target": "issue:PAY-42",
          "edge_id": "incident:INC-17|LED_TO|issue:PAY-42",
          "tool": "decision_trace",
          "traversal_from": "incident:INC-17",
          "traversal_to": "issue:PAY-42",
          "evidence": {
            "tool": "decision_trace",
            "node_ids": [
              "incident:INC-17",
              "issue:PAY-42"
            ],
            "edge_ids": [
              "incident:INC-17|LED_TO|issue:PAY-42"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "incident:INC-17|LED_TO|issue:PAY-42"
              ]
            ]
          },
          "explanation": "Stored relationship: incident:INC-17 \u2014LED_TO\u2192 issue:PAY-42.",
          "citation_ids": []
        }
      ]
    },
    {
      "id": "decision_trace/decision_to_investigation",
      "path_id": "decision_to_investigation",
      "tool": "decision_trace",
      "support_status": "supported",
      "steps": [
        {
          "number": 1,
          "sequence_id": "decision_trace/decision_to_investigation",
          "source": "decision:D-007",
          "type": "SUPPORTED_BY",
          "target": "issue:PAY-42",
          "edge_id": "decision:D-007|SUPPORTED_BY|issue:PAY-42",
          "tool": "decision_trace",
          "traversal_from": "decision:D-007",
          "traversal_to": "issue:PAY-42",
          "evidence": {
            "tool": "decision_trace",
            "node_ids": [
              "decision:D-007",
              "issue:PAY-42"
            ],
            "edge_ids": [
              "decision:D-007|SUPPORTED_BY|issue:PAY-42"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "decision:D-007|SUPPORTED_BY|issue:PAY-42"
              ]
            ]
          },
          "explanation": "Stored relationship: decision:D-007 \u2014SUPPORTED_BY\u2192 issue:PAY-42.",
          "citation_ids": []
        }
      ]
    },
    {
      "id": "decision_trace/decision_to_discussion",
      "path_id": "decision_to_discussion",
      "tool": "decision_trace",
      "support_status": "supported",
      "steps": [
        {
          "number": 1,
          "sequence_id": "decision_trace/decision_to_discussion",
          "source": "decision:D-007",
          "type": "SUPPORTED_BY",
          "target": "message:payment-perf-7",
          "edge_id": "decision:D-007|SUPPORTED_BY|message:payment-perf-7",
          "tool": "decision_trace",
          "traversal_from": "decision:D-007",
          "traversal_to": "message:payment-perf-7",
          "evidence": {
            "tool": "decision_trace",
            "node_ids": [
              "decision:D-007",
              "message:payment-perf-7"
            ],
            "edge_ids": [
              "decision:D-007|SUPPORTED_BY|message:payment-perf-7"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "decision:D-007|SUPPORTED_BY|message:payment-perf-7"
              ]
            ]
          },
          "explanation": "Stored relationship: decision:D-007 \u2014SUPPORTED_BY\u2192 message:payment-perf-7.",
          "citation_ids": []
        }
      ]
    },
    {
      "id": "decision_trace/decision_to_documentation",
      "path_id": "decision_to_documentation",
      "tool": "decision_trace",
      "support_status": "supported",
      "steps": [
        {
          "number": 1,
          "sequence_id": "decision_trace/decision_to_documentation",
          "source": "decision:D-007",
          "type": "DOCUMENTED_IN",
          "target": "doc:ADR-7",
          "edge_id": "decision:D-007|DOCUMENTED_IN|doc:ADR-7",
          "tool": "decision_trace",
          "traversal_from": "decision:D-007",
          "traversal_to": "doc:ADR-7",
          "evidence": {
            "tool": "decision_trace",
            "node_ids": [
              "decision:D-007",
              "doc:ADR-7"
            ],
            "edge_ids": [
              "decision:D-007|DOCUMENTED_IN|doc:ADR-7"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "decision:D-007|DOCUMENTED_IN|doc:ADR-7"
              ]
            ]
          },
          "explanation": "Stored relationship: decision:D-007 \u2014DOCUMENTED_IN\u2192 doc:ADR-7.",
          "citation_ids": []
        }
      ]
    },
    {
      "id": "decision_trace/decision_to_current_architecture",
      "path_id": "decision_to_current_architecture",
      "tool": "decision_trace",
      "support_status": "supported",
      "steps": [
        {
          "number": 1,
          "sequence_id": "decision_trace/decision_to_current_architecture",
          "source": "decision:D-007",
          "type": "IMPLEMENTED_BY",
          "target": "commit:8fae2",
          "edge_id": "decision:D-007|IMPLEMENTED_BY|commit:8fae2",
          "tool": "decision_trace",
          "traversal_from": "decision:D-007",
          "traversal_to": "commit:8fae2",
          "evidence": {
            "tool": "decision_trace",
            "node_ids": [
              "decision:D-007",
              "commit:8fae2"
            ],
            "edge_ids": [
              "decision:D-007|IMPLEMENTED_BY|commit:8fae2"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "decision:D-007|IMPLEMENTED_BY|commit:8fae2"
              ]
            ]
          },
          "explanation": "Stored relationship: decision:D-007 \u2014IMPLEMENTED_BY\u2192 commit:8fae2.",
          "citation_ids": []
        },
        {
          "number": 2,
          "sequence_id": "decision_trace/decision_to_current_architecture",
          "source": "commit:8fae2",
          "type": "CHANGES",
          "target": "service:payment-service",
          "edge_id": "commit:8fae2|CHANGES|service:payment-service",
          "tool": "decision_trace",
          "traversal_from": "commit:8fae2",
          "traversal_to": "service:payment-service",
          "evidence": {
            "tool": "decision_trace",
            "node_ids": [
              "commit:8fae2",
              "service:payment-service"
            ],
            "edge_ids": [
              "commit:8fae2|CHANGES|service:payment-service"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "commit:8fae2|CHANGES|service:payment-service"
              ]
            ]
          },
          "explanation": "Stored relationship: commit:8fae2 \u2014CHANGES\u2192 service:payment-service.",
          "citation_ids": []
        },
        {
          "number": 3,
          "sequence_id": "decision_trace/decision_to_current_architecture",
          "source": "service:payment-service",
          "type": "USES",
          "target": "tech:redis",
          "edge_id": "service:payment-service|USES|tech:redis",
          "tool": "decision_trace",
          "traversal_from": "service:payment-service",
          "traversal_to": "tech:redis",
          "evidence": {
            "tool": "decision_trace",
            "node_ids": [
              "service:payment-service",
              "tech:redis"
            ],
            "edge_ids": [
              "service:payment-service|USES|tech:redis"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:payment-service|USES|tech:redis"
              ]
            ]
          },
          "explanation": "Stored relationship: service:payment-service \u2014USES\u2192 tech:redis.",
          "citation_ids": []
        }
      ]
    },
    {
      "id": "impact_analysis/service:payment-service",
      "path_id": "service:payment-service",
      "tool": "impact_analysis",
      "support_status": "partially_supported",
      "steps": [
        {
          "number": 1,
          "sequence_id": "impact_analysis/service:payment-service",
          "source": "service:payment-service",
          "type": "USES",
          "target": "tech:redis",
          "edge_id": "service:payment-service|USES|tech:redis",
          "tool": "impact_analysis",
          "traversal_from": "tech:redis",
          "traversal_to": "service:payment-service",
          "evidence": {
            "tool": "impact_analysis",
            "node_ids": [
              "service:payment-service",
              "tech:redis"
            ],
            "edge_ids": [
              "service:payment-service|USES|tech:redis"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:payment-service|USES|tech:redis"
              ]
            ]
          },
          "explanation": "Stored relationship: service:payment-service \u2014USES\u2192 tech:redis. Traversal proceeds from dependency to dependent; this does not establish failure propagation.",
          "citation_ids": []
        }
      ]
    },
    {
      "id": "impact_analysis/service:checkout-service",
      "path_id": "service:checkout-service",
      "tool": "impact_analysis",
      "support_status": "partially_supported",
      "steps": [
        {
          "number": 1,
          "sequence_id": "impact_analysis/service:checkout-service",
          "source": "service:payment-service",
          "type": "USES",
          "target": "tech:redis",
          "edge_id": "service:payment-service|USES|tech:redis",
          "tool": "impact_analysis",
          "traversal_from": "tech:redis",
          "traversal_to": "service:payment-service",
          "evidence": {
            "tool": "impact_analysis",
            "node_ids": [
              "service:payment-service",
              "tech:redis"
            ],
            "edge_ids": [
              "service:payment-service|USES|tech:redis"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:payment-service|USES|tech:redis"
              ]
            ]
          },
          "explanation": "Stored relationship: service:payment-service \u2014USES\u2192 tech:redis. Traversal proceeds from dependency to dependent; this does not establish failure propagation.",
          "citation_ids": []
        },
        {
          "number": 2,
          "sequence_id": "impact_analysis/service:checkout-service",
          "source": "service:checkout-service",
          "type": "DEPENDS_ON",
          "target": "service:payment-service",
          "edge_id": "service:checkout-service|DEPENDS_ON|service:payment-service",
          "tool": "impact_analysis",
          "traversal_from": "service:payment-service",
          "traversal_to": "service:checkout-service",
          "evidence": {
            "tool": "impact_analysis",
            "node_ids": [
              "service:checkout-service",
              "service:payment-service"
            ],
            "edge_ids": [
              "service:checkout-service|DEPENDS_ON|service:payment-service"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:checkout-service|DEPENDS_ON|service:payment-service"
              ]
            ]
          },
          "explanation": "Stored relationship: service:checkout-service \u2014DEPENDS_ON\u2192 service:payment-service. Traversal proceeds from dependency to dependent; this does not establish failure propagation.",
          "citation_ids": []
        }
      ]
    },
    {
      "id": "impact_analysis/service:order-service",
      "path_id": "service:order-service",
      "tool": "impact_analysis",
      "support_status": "partially_supported",
      "steps": [
        {
          "number": 1,
          "sequence_id": "impact_analysis/service:order-service",
          "source": "service:payment-service",
          "type": "USES",
          "target": "tech:redis",
          "edge_id": "service:payment-service|USES|tech:redis",
          "tool": "impact_analysis",
          "traversal_from": "tech:redis",
          "traversal_to": "service:payment-service",
          "evidence": {
            "tool": "impact_analysis",
            "node_ids": [
              "service:payment-service",
              "tech:redis"
            ],
            "edge_ids": [
              "service:payment-service|USES|tech:redis"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:payment-service|USES|tech:redis"
              ]
            ]
          },
          "explanation": "Stored relationship: service:payment-service \u2014USES\u2192 tech:redis. Traversal proceeds from dependency to dependent; this does not establish failure propagation.",
          "citation_ids": []
        },
        {
          "number": 2,
          "sequence_id": "impact_analysis/service:order-service",
          "source": "service:checkout-service",
          "type": "DEPENDS_ON",
          "target": "service:payment-service",
          "edge_id": "service:checkout-service|DEPENDS_ON|service:payment-service",
          "tool": "impact_analysis",
          "traversal_from": "service:payment-service",
          "traversal_to": "service:checkout-service",
          "evidence": {
            "tool": "impact_analysis",
            "node_ids": [
              "service:checkout-service",
              "service:payment-service"
            ],
            "edge_ids": [
              "service:checkout-service|DEPENDS_ON|service:payment-service"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:checkout-service|DEPENDS_ON|service:payment-service"
              ]
            ]
          },
          "explanation": "Stored relationship: service:checkout-service \u2014DEPENDS_ON\u2192 service:payment-service. Traversal proceeds from dependency to dependent; this does not establish failure propagation.",
          "citation_ids": []
        },
        {
          "number": 3,
          "sequence_id": "impact_analysis/service:order-service",
          "source": "service:order-service",
          "type": "DEPENDS_ON",
          "target": "service:checkout-service",
          "edge_id": "service:order-service|DEPENDS_ON|service:checkout-service",
          "tool": "impact_analysis",
          "traversal_from": "service:checkout-service",
          "traversal_to": "service:order-service",
          "evidence": {
            "tool": "impact_analysis",
            "node_ids": [
              "service:order-service",
              "service:checkout-service"
            ],
            "edge_ids": [
              "service:order-service|DEPENDS_ON|service:checkout-service"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:order-service|DEPENDS_ON|service:checkout-service"
              ]
            ]
          },
          "explanation": "Stored relationship: service:order-service \u2014DEPENDS_ON\u2192 service:checkout-service. Traversal proceeds from dependency to dependent; this does not establish failure propagation.",
          "citation_ids": []
        }
      ]
    }
  ]
};

export function changeWithPlayback() {
  const result = changeWithOrderedPaths();
  result.data.trace_playback = structuredClone(playback);
  return result;
}
