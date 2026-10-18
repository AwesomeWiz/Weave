import { AlertTriangle, Box, Building2, CircleHelp, Database, FileText, GitBranch, GitCommitHorizontal, Github, MessageSquare, Server, Ticket, UserRound } from 'lucide-react';

export default function EntityIcon({ type, size = 20 }: { type: string; size?: number }) {
  const Icon = ({ Incident: AlertTriangle, Service: Server, Technology: Database,
    Decision: FileText, Document: FileText, Chunk: FileText, Issue: Ticket, Person: UserRound,
    Message: MessageSquare, Repository: Github, Commit: GitCommitHorizontal,
    Team: Building2, Project: Box, Relationship: GitBranch } as const)[type as 'Service'] ?? CircleHelp;
  return <Icon size={size} strokeWidth={1.7} aria-hidden="true" />;
}
