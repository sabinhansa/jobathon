export type HealthResponse = {
  status: string;
  model: string;
  database: string;
  embeddings: string;
  ollama: string;
  chroma: string;
};

export type CVListItem = {
  id: string;
  name: string;
  filename: string;
  created_at: string;
  updated_at: string;
};

export type RequirementMatch = {
  requirement: string;
  importance: "required" | "nice_to_have" | "responsibility" | "technology";
  status: "strong_match" | "partial_match" | "missing" | "unclear";
  cv_evidence: string[];
  explanation: string;
};

export type AnalyzeResponse = {
  analysis_id: string;
  overall_score: number;
  confidence: "low" | "medium" | "high";
  summary: string;
  requirement_matches: RequirementMatch[];
  strengths: string[];
  gaps: string[];
  cv_improvements: Array<{
    target_section: string;
    original_evidence: string;
    suggested_bullet: string;
    why_it_helps: string;
  }>;
  cover_letter: string;
  recruiter_message: string;
  interview_prep: string[];
  warnings: string[];
  markdown_report: string;
};

export type AnalyzeRequest = {
  cv_id: string;
  job_text: string;
  job_url?: string;
  job_title?: string;
  company?: string;
  mode: "fast" | "deep";
};

