export interface Source {
  text: string
  source: string
  subject: string
  file_type: string
  file_size_kb: number
  chunk_index: number
  total_chunks: number
  char_start: number
  char_end: number
  chunk_size: number
  ingested_at: string
  pinecone_score: number
  rerank_score: number | null
  rerank_rank: number | null
}

export interface Message {
  id: string
  role: 'user' | 'bot'
  content: string
  sources?: Source[]
  streaming?: boolean
}

export interface IngestEntry {
  subject: string
  file_type: string
  file_size_kb: number
  total_chunks: number
  ingested_at: string
}

export type SubjectKey = 'mathematics' | 'science' | 'english' | 'social studies' | string

export const SUBJECT_META: Record<string, { color: string; glow: string; border: string; badge: string }> = {
  mathematics:    { color: 'text-amber-400',   glow: 'shadow-glow-amber',   border: 'border-amber-500/40',   badge: 'bg-amber-500/20 text-amber-300'   },
  science:        { color: 'text-emerald-400', glow: 'shadow-glow-emerald', border: 'border-emerald-500/40', badge: 'bg-emerald-500/20 text-emerald-300' },
  english:        { color: 'text-blue-400',    glow: 'shadow-glow-blue',    border: 'border-blue-500/40',    badge: 'bg-blue-500/20 text-blue-300'       },
  'social studies':{ color: 'text-violet-400', glow: 'shadow-glow-violet',  border: 'border-violet-500/40',  badge: 'bg-violet-500/20 text-violet-300'   },
}

export function getSubjectMeta(subject: string) {
  return SUBJECT_META[subject.toLowerCase()] ?? {
    color: 'text-indigo-400', glow: 'shadow-glow-indigo',
    border: 'border-indigo-500/40', badge: 'bg-indigo-500/20 text-indigo-300',
  }
}
