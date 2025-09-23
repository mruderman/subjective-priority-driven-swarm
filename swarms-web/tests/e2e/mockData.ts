import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

export type MockAgent = {
  id: string;
  name: string;
  model: string;
  created_at: string;
};

type MockData = {
  agents: MockAgent[];
  secretaryMinutes: string;
  agentResponse: string;
};

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const mockDataPath = path.resolve(currentDir, './mock-data.json');

const raw = readFileSync(mockDataPath, 'utf-8');
const parsed = JSON.parse(raw) as Partial<MockData>;

const normalizeAgents = (agents: unknown): MockAgent[] => {
  if (!Array.isArray(agents)) {
    return [];
  }

  return agents
    .map((agent, index) => {
      if (typeof agent !== 'object' || agent === null) {
        return null;
      }

      const candidate = agent as Record<string, unknown>;
      return {
        id: typeof candidate.id === 'string' ? candidate.id : `mock-agent-${index + 1}`,
        name: typeof candidate.name === 'string' ? candidate.name : `Mock Agent ${index + 1}`,
        model: typeof candidate.model === 'string' ? candidate.model : 'openai/gpt-4',
        created_at:
          typeof candidate.created_at === 'string' ? candidate.created_at : '2024-01-01',
      } satisfies MockAgent;
    })
    .filter((agent): agent is MockAgent => agent !== null);
};

export const mockData: MockData = {
  agents: normalizeAgents(parsed.agents),
  secretaryMinutes:
    typeof parsed.secretaryMinutes === 'string'
      ? parsed.secretaryMinutes
      : 'Meeting Minutes\n- Agenda review\n- Decisions recorded',
  agentResponse:
    typeof parsed.agentResponse === 'string'
      ? parsed.agentResponse
      : 'AI advancements look promising with collaborative intelligence.',
};

export const cloneAgents = (agents: MockAgent[]): MockAgent[] =>
  agents.map((agent) => ({ ...agent }));
