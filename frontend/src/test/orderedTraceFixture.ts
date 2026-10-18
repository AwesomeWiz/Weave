// Test only: actual merged teammate tools over the explicit offline database double.
// No runtime fixture fallback. Original graph objects already exist in changeFixture.
import { changeFixture } from './changeFixture';
import type { ChangeEvidenceReference, ChangeResponse, TraceRelationshipPath } from '../types';

const historicalEvidence: { relationship_paths: TraceRelationshipPath[]; evidence: ChangeEvidenceReference } = {
  "relationship_paths": [
    {
      "id": "incident_to_investigation",
      "steps": [
        {
          "source": "incident:INC-17",
          "type": "LED_TO",
          "target": "issue:PAY-42"
        }
      ]
    },
    {
      "id": "decision_to_investigation",
      "steps": [
        {
          "source": "decision:D-007",
          "type": "SUPPORTED_BY",
          "target": "issue:PAY-42"
        }
      ]
    },
    {
      "id": "decision_to_discussion",
      "steps": [
        {
          "source": "decision:D-007",
          "type": "SUPPORTED_BY",
          "target": "message:payment-perf-7"
        }
      ]
    },
    {
      "id": "decision_to_documentation",
      "steps": [
        {
          "source": "decision:D-007",
          "type": "DOCUMENTED_IN",
          "target": "doc:ADR-7"
        }
      ]
    },
    {
      "id": "decision_to_current_architecture",
      "steps": [
        {
          "source": "decision:D-007",
          "type": "IMPLEMENTED_BY",
          "target": "commit:8fae2"
        },
        {
          "source": "commit:8fae2",
          "type": "CHANGES",
          "target": "service:payment-service"
        },
        {
          "source": "service:payment-service",
          "type": "USES",
          "target": "tech:redis"
        }
      ]
    }
  ],
  "evidence": {
    "tool": "decision_trace",
    "node_ids": [
      "incident:INC-17",
      "doc:ADR-7",
      "issue:PAY-42",
      "message:payment-perf-7",
      "decision:D-007",
      "commit:8fae2",
      "service:payment-service",
      "tech:redis",
      "chunk:commit:8fae2:0",
      "chunk:doc:ADR-7:0",
      "chunk:issue:PAY-42:0",
      "chunk:message:payment-perf-7:0"
    ],
    "edge_ids": [
      "decision:D-007|AFFECTS|service:payment-service",
      "decision:D-007|INTRODUCES|tech:redis",
      "incident:INC-17|LED_TO|issue:PAY-42",
      "decision:D-007|DOCUMENTED_IN|doc:ADR-7",
      "decision:D-007|SUPPORTED_BY|issue:PAY-42",
      "decision:D-007|SUPPORTED_BY|message:payment-perf-7",
      "decision:D-007|IMPLEMENTED_BY|commit:8fae2",
      "commit:8fae2|CHANGES|service:payment-service",
      "service:payment-service|USES|tech:redis",
      "chunk:commit:8fae2:0|FROM_COMMIT|commit:8fae2",
      "chunk:doc:ADR-7:0|FROM_DOCUMENT|doc:ADR-7",
      "chunk:issue:PAY-42:0|FROM_ISSUE|issue:PAY-42",
      "chunk:message:payment-perf-7:0|FROM_MESSAGE|message:payment-perf-7"
    ],
    "source_ids": [
      "commit:8fae2",
      "doc:ADR-7",
      "issue:PAY-42",
      "message:payment-perf-7"
    ],
    "relationship_paths": [
      [
        "incident:INC-17|LED_TO|issue:PAY-42"
      ],
      [
        "decision:D-007|SUPPORTED_BY|issue:PAY-42"
      ],
      [
        "decision:D-007|SUPPORTED_BY|message:payment-perf-7"
      ],
      [
        "decision:D-007|DOCUMENTED_IN|doc:ADR-7"
      ],
      [
        "decision:D-007|IMPLEMENTED_BY|commit:8fae2",
        "commit:8fae2|CHANGES|service:payment-service",
        "service:payment-service|USES|tech:redis"
      ]
    ]
  }
};

export function changeWithOrderedPaths(): ChangeResponse {
  const result = structuredClone(changeFixture);
  result.data.historical_context.relationship_paths = structuredClone(historicalEvidence.relationship_paths);
  result.data.historical_context.evidence = structuredClone(historicalEvidence.evidence);
  result.data.tool_support.decision_trace!.evidence = structuredClone(historicalEvidence.evidence);
  return result;
}
