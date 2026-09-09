#!/usr/bin/env python3
"""Two-level benchmark taxonomy and the source-token lexicon behind it.

Every label a record receives must be traceable to a token in a named source
field, or to a documented text pattern over the record's own name/description.
Nothing here invents a measurement: the taxonomy describes what a benchmark
tests, and leaves scores, dates and counts to the catalog census.

Axes
----
L1/L2 answer "what capability is under test". They are a single primary label
per record so that a Sankey or a stacked area has one flow per benchmark.

`modality`, `interaction` and `operational` are recorded separately, because a
benchmark's input type and its interaction paradigm are orthogonal to its
subject. Folding them into one flat list is what makes the live five-way chart
collapse 91 agentic coding benchmarks into `Code` and lose the agentic signal.

Primary-label rule
------------------
Subject domain beats interaction paradigm beats modality. An agentic coding
benchmark is `coding_se` with `interaction=agentic`; a visual maths benchmark is
`math_logic` with `modality=image`. `agentic_tool_use` and `multimodal_perception`
stay as L1 for records whose object of measurement *is* the agent loop or the
perception itself, with no dominant subject domain.

Generic tokens
--------------
`reasoning` sits on 428 of 687 LLM Stats records (62%) and `general` on 153. They
do not discriminate, so they carry a fractional weight and win only when a record
offers no subject evidence at all. They are still recorded as facets.
"""

# --- L1 -----------------------------------------------------------------

L1 = {
    "agentic_tool_use": "Agentic & Tool Use",
    "coding_se": "Coding & Software Engineering",
    "math_logic": "Math & Logical Reasoning",
    "science_research": "Science & Research",
    "knowledge_factuality": "Knowledge & Factuality",
    "language_communication": "Language & Communication",
    "multimodal_perception": "Multimodal Perception & Generation",
    "safety_security": "Safety, Security & Alignment",
    "applied_verticals": "Applied & Professional Domains",
    "general_composite": "General & Composite Index",
    "other": "Other / Unclassified",
}

# The five L1 classes that name a subject matter rather than a capability layer.
# When one of them is supported and the leading candidate is only a paradigm
# (`agentic_tool_use`) or a modality (`multimodal_perception`), the subject wins
# the primary label and the paradigm or modality is kept as a facet. This is the
# rule that keeps an agentic coding benchmark under `coding_se` and a visual
# physics benchmark under `science_research`, without discarding either signal.
#
# `knowledge_factuality` and `language_communication` are layers too: OpenCompass
# puts `Knowledge` on 40 records and `Understanding` on 67, frequently over a
# benchmark whose actual subject is medicine, finance or chemistry. A named
# subject therefore also wins against them, which is what moves MedBench to
# healthcare and LongCodeBench to code with `op:long_context` kept as a facet.
SUBJECT_DOMAINS = frozenset({
    "coding_se", "math_logic", "science_research", "applied_verticals", "safety_security",
})
LAYER_DOMAINS = frozenset({
    "agentic_tool_use", "multimodal_perception",
    "knowledge_factuality", "language_communication",
})
# A subject needs at least this share of the leading layer's weight to override.
SUBJECT_OVERRIDE_RATIO = 0.5

# Deterministic tie-break when two L1 candidates hold the same weight.
# Specific subject domains first; paradigm and modality last.
L1_PRIORITY = [
    "coding_se",
    "math_logic",
    "science_research",
    "applied_verticals",
    "safety_security",
    "agentic_tool_use",
    "multimodal_perception",
    "knowledge_factuality",
    "language_communication",
    "general_composite",
    "other",
]

L2 = {
    "agentic_tool_use": [
        "tool_function_calling", "computer_gui_use", "web_browsing_deep_research",
        "os_terminal", "workflow_task_execution", "multi_agent_collaboration",
        "embodied_agent", "agent_general",
    ],
    "coding_se": [
        "code_generation", "swe_repo_issue", "competitive_programming",
        "code_reasoning_execution", "frontend_ui", "data_sql", "code_security",
        "hardware_eda", "code_general",
    ],
    "math_logic": [
        "competition_math", "math_word_problems", "formal_theorem_proving",
        "logical_puzzle_reasoning", "abstract_reasoning", "math_general",
    ],
    "science_research": [
        "physics", "chemistry", "biology_life_science", "general_science_qa",
        "research_engineering_ml", "scientific_reasoning", "science_general",
    ],
    "knowledge_factuality": [
        "world_knowledge_qa", "exam_academic", "factuality_hallucination",
        "commonsense", "knowledge_general",
    ],
    "language_communication": [
        "reading_comprehension", "multilingual_translation", "instruction_following",
        "creative_writing", "summarization", "dialogue_roleplay",
        "human_preference_chat", "long_context_text", "language_general",
    ],
    "multimodal_perception": [
        "image_understanding_vqa", "video_understanding", "audio_speech",
        "ocr_document", "chart_diagram", "visual_generation_editing", "spatial_3d",
        "embodied_perception", "cross_modal_reasoning", "multimodal_general",
    ],
    "safety_security": [
        "harmfulness_alignment", "jailbreak_robustness", "cybersecurity_offensive",
        "privacy", "bias_fairness", "safety_general",
    ],
    "applied_verticals": [
        "healthcare_medical", "legal", "finance_economics", "business_productivity",
        "education", "vertical_general",
    ],
    "general_composite": [
        "aggregate_index", "general_capability", "arena_elo", "robustness_consistency",
    ],
    "other": ["unclassified"],
}

# L2 fallbacks. A token like `code` or `agents` carries a high-weight field but
# says nothing beyond its L1, so it must not outrank a specific L2 that a lower
# weight field or a text pattern supplied. These are used only when no specific
# L2 under the chosen L1 received a vote.
GENERIC_L2 = frozenset({
    "agent_general", "code_general", "math_general", "science_general",
    "knowledge_general", "language_general", "multimodal_general",
    "safety_general", "vertical_general", "general_capability", "unclassified",
})

# --- source field weights -----------------------------------------------
# OpenCompass `dimensions` and the curated model-report `domain` are the
# publishers' own first-level labels; free tags and prose rank below them.
FIELD_WEIGHT = {
    "oc.dimensions": 10.0,
    "mc.domain": 10.0,
    "aa.categories": 10.0,
    "ls.categories": 6.0,
    "oc.basic_tags": 6.0,
    "oc.card_tags": 3.0,
    "text.name": 2.5,
    "text.description": 2.0,
}
GENERIC_MULTIPLIER = 0.15

# --- non-topical tokens -------------------------------------------------
# Verified against the source columns: `Unsupported` is support_online_eval
# rendered as a badge (448/448), `Open-Source` is certificate_level (66/66),
# `LLM`/`VLM` name the model type, `topic_tags` carry conference venues.
NOISE = {
    "unsupported": "support_online_eval flag",
    "supported": "support_online_eval flag",
    "不支持": "support_online_eval flag",
    "支持": "support_online_eval flag",
    "open-source": "certificate_level",
    "开源收录": "certificate_level",
    "co-built": "certificate_level",
    "合作共建": "certificate_level",
    "official": "certificate_level",
    "官方自建": "certificate_level",
    "未录入": "certificate_level",
    "llm": "model type",
    "大语言模型": "model type",
    "vlm": "model type",
    "多模态模型": "model type",
    "mllm": "model type",
    "mllms": "model type",
    "lrm": "model type",
    "lam": "model type",
    "large vision language models": "model type",
    "pulsar vlm": "model type",
    "neurips 2024": "venue",
    "acl 2024": "venue",
    "naacl 2024": "venue",
    "naacl 2025": "venue",
    "icml 2025": "venue",
    "benchmark": "non-topical",
    "dataset and benchmark": "non-topical",
    "other": "no signal",
    "其他": "no signal",
    "artifactsbench": "benchmark name",
    "mmar": "benchmark name",
    "mer": "benchmark name",
    "ams": "benchmark name",
}


def _e(l1, l2, facets=(), generic=False):
    """A token's contribution. `l1=None` records facets only, casting no L1 vote."""
    return {"l1": l1, "l2": l2, "facets": list(facets), "generic": generic}


# --- token lexicon ------------------------------------------------------
# Keys are lowercased source tokens. Chinese keys are the OpenCompass twins of
# the English labels in the same field, kept so a CJK-only tag still resolves.
TOKEN_MAP = {
    # ---- agentic / tool use
    "agent": _e("agentic_tool_use", "agent_general", ["interaction:agentic"]),
    "agents": _e("agentic_tool_use", "agent_general", ["interaction:agentic"]),
    "agentic": _e("agentic_tool_use", "agent_general", ["interaction:agentic"]),
    "智能体": _e("agentic_tool_use", "agent_general", ["interaction:agentic"]),
    "agent evaluation": _e("agentic_tool_use", "agent_general", ["interaction:agentic"]),
    "ai assistant": _e("agentic_tool_use", "agent_general", ["interaction:agentic"]),
    "tool_calling": _e("agentic_tool_use", "tool_function_calling", ["interaction:agentic", "op:tool_calling"]),
    "tool-use": _e("agentic_tool_use", "tool_function_calling", ["interaction:agentic", "op:tool_calling"]),
    "tool_use": _e("agentic_tool_use", "tool_function_calling", ["interaction:agentic", "op:tool_calling"]),
    "computer_use": _e("agentic_tool_use", "computer_gui_use", ["interaction:agentic", "modality:gui"]),
    "task execution": _e("agentic_tool_use", "workflow_task_execution", ["interaction:agentic"]),
    "任务执行": _e("agentic_tool_use", "workflow_task_execution", ["interaction:agentic"]),
    "task planning": _e("agentic_tool_use", "workflow_task_execution", ["interaction:agentic"]),
    "in-the-wild tasks": _e("agentic_tool_use", "workflow_task_execution", ["interaction:agentic"]),
    "multimodal & tool-use reasoning": _e("agentic_tool_use", "tool_function_calling", ["interaction:agentic", "modality:multimodal"]),
    "search": _e("agentic_tool_use", "web_browsing_deep_research", ["op:retrieval_rag"]),
    "deep research": _e("agentic_tool_use", "web_browsing_deep_research", ["interaction:agentic", "op:retrieval_rag"]),
    "retrieval": _e("agentic_tool_use", "web_browsing_deep_research", ["op:retrieval_rag"]),
    "检索": _e("agentic_tool_use", "web_browsing_deep_research", ["op:retrieval_rag"]),
    "rag": _e("agentic_tool_use", "web_browsing_deep_research", ["op:retrieval_rag"]),
    "grounding": _e("agentic_tool_use", "web_browsing_deep_research", ["op:retrieval_rag"]),
    "interactive benchmark": _e("agentic_tool_use", "agent_general", ["interaction:agentic"]),
    "code agent": _e("coding_se", "swe_repo_issue", ["interaction:agentic"]),
    "coding_agent": _e("coding_se", "swe_repo_issue", ["interaction:agentic"]),
    "legal agent": _e("applied_verticals", "legal", ["interaction:agentic"]),
    "embodied interaction": _e("agentic_tool_use", "embodied_agent", ["interaction:agentic", "modality:embodied"]),
    "具身交互": _e("agentic_tool_use", "embodied_agent", ["interaction:agentic", "modality:embodied"]),
    "embodied decision making": _e("agentic_tool_use", "embodied_agent", ["interaction:agentic", "modality:embodied"]),
    "navigation": _e("agentic_tool_use", "embodied_agent", ["interaction:agentic", "modality:embodied"]),
    "manipulate": _e("agentic_tool_use", "embodied_agent", ["interaction:agentic", "modality:embodied"]),
    "robotics": _e("agentic_tool_use", "embodied_agent", ["interaction:agentic", "modality:embodied"]),
    "embodied": _e("agentic_tool_use", "embodied_agent", ["interaction:agentic", "modality:embodied"]),
    "embodied ai": _e("agentic_tool_use", "embodied_agent", ["interaction:agentic", "modality:embodied"]),
    "具身智能": _e("agentic_tool_use", "embodied_agent", ["interaction:agentic", "modality:embodied"]),
    "worldmodel": _e("agentic_tool_use", "embodied_agent", ["modality:embodied"]),
    "simulation": _e("agentic_tool_use", "workflow_task_execution", ["interaction:agentic"]),
    "productivity": _e("applied_verticals", "business_productivity", ["interaction:agentic"]),

    # ---- coding
    "code": _e("coding_se", "code_general"),
    "coding": _e("coding_se", "code_general"),
    "代码": _e("coding_se", "code_general"),
    "代码工程": _e("coding_se", "code_general"),
    "competitive programming": _e("coding_se", "competitive_programming"),
    "github issue resolution": _e("coding_se", "swe_repo_issue", ["interaction:agentic"]),
    "swe-bench": _e("coding_se", "swe_repo_issue", ["interaction:agentic"]),
    "open-source software": _e("coding_se", "swe_repo_issue"),
    "automatic test augmentation": _e("coding_se", "code_generation"),
    "frontend_development": _e("coding_se", "frontend_ui"),
    "data_analysis": _e("coding_se", "data_sql"),
    "structured_output": _e("coding_se", "code_general", ["op:structured_output"]),
    "systems": _e("coding_se", "code_general"),
    "lean4": _e("math_logic", "formal_theorem_proving"),
    "eda": _e("coding_se", "hardware_eda"),
    "circuit": _e("coding_se", "hardware_eda"),
    "memory safety": _e("coding_se", "code_security", ["op:safety_probe"]),
    "engineering": _e("coding_se", "code_general"),
    "capabilities of on-device llms": _e("coding_se", "code_general"),

    # ---- math & logic
    "math": _e("math_logic", "math_general"),
    "数学": _e("math_logic", "math_general"),
    "数理能力": _e("math_logic", "math_general"),
    "gsm8k": _e("math_logic", "math_word_problems"),
    "combinatorics": _e("math_logic", "competition_math"),
    "problem similarity": _e("math_logic", "math_general"),
    "reasoning": _e("math_logic", "logical_puzzle_reasoning", ["op:reasoning"], generic=True),
    "推理": _e("math_logic", "logical_puzzle_reasoning", ["op:reasoning"], generic=True),
    "逻辑推理": _e("math_logic", "logical_puzzle_reasoning", ["op:reasoning"]),
    "strong reasoning": _e("math_logic", "abstract_reasoning", ["op:reasoning"]),
    "强推理": _e("math_logic", "abstract_reasoning", ["op:reasoning"]),
    "self-critique": _e("math_logic", "logical_puzzle_reasoning", ["op:reasoning"]),
    "consistency": _e("math_logic", "logical_puzzle_reasoning", ["op:reasoning"]),

    # ---- science & research
    "science": _e("science_research", "science_general"),
    "科学智能": _e("science_research", "science_general"),
    "ai for science": _e("science_research", "science_general"),
    "scientific reasoning": _e("science_research", "scientific_reasoning"),
    "科学推理": _e("science_research", "scientific_reasoning"),
    "physics": _e("science_research", "physics"),
    "物理": _e("science_research", "physics"),
    "物理智能": _e("science_research", "physics"),
    "chemistry": _e("science_research", "chemistry"),
    "化学": _e("science_research", "chemistry"),
    "biology": _e("science_research", "biology_life_science"),
    "生物": _e("science_research", "biology_life_science"),
    "aneurysm": _e("science_research", "biology_life_science"),
    "computational fluid dynamics": _e("science_research", "physics"),
    "lab protocol": _e("science_research", "scientific_reasoning"),
    "ai_research": _e("science_research", "research_engineering_ml"),
    "research": _e("science_research", "research_engineering_ml"),
    "psychology": _e("science_research", "general_science_qa"),

    # ---- knowledge & factuality
    "knowledge": _e("knowledge_factuality", "knowledge_general"),
    "知识": _e("knowledge_factuality", "knowledge_general"),
    "知识储备": _e("knowledge_factuality", "knowledge_general"),
    "visual knowledge": _e("knowledge_factuality", "world_knowledge_qa", ["modality:image"]),
    "examination": _e("knowledge_factuality", "exam_academic", ["op:examination"]),
    "学科": _e("knowledge_factuality", "exam_academic", ["op:examination"]),
    "教育": _e("applied_verticals", "education"),
    "factuality": _e("knowledge_factuality", "factuality_hallucination"),
    "faithfulness": _e("knowledge_factuality", "factuality_hallucination"),
    "factual reliability": _e("knowledge_factuality", "factuality_hallucination"),
    "事实可靠性": _e("knowledge_factuality", "factuality_hallucination"),
    "fact-checking": _e("knowledge_factuality", "factuality_hallucination"),
    "hallucination": _e("knowledge_factuality", "factuality_hallucination"),
    "question_answering": _e("knowledge_factuality", "world_knowledge_qa"),

    # ---- language & communication
    "language": _e("language_communication", "language_general"),
    "语言": _e("language_communication", "language_general"),
    "understanding": _e("language_communication", "reading_comprehension"),
    "理解": _e("language_communication", "reading_comprehension"),
    "comprehension": _e("language_communication", "reading_comprehension"),
    "语言理解": _e("language_communication", "reading_comprehension"),
    "nlp": _e("language_communication", "language_general"),
    "multilingual": _e("language_communication", "multilingual_translation", ["op:multilingual"]),
    "多语种": _e("language_communication", "multilingual_translation", ["op:multilingual"]),
    "communication": _e("language_communication", "dialogue_roleplay"),
    "roleplay": _e("language_communication", "dialogue_roleplay"),
    "human_preference": _e("language_communication", "human_preference_chat"),
    "instruction_following": _e("language_communication", "instruction_following", ["op:instruction_following"]),
    "instruction following": _e("language_communication", "instruction_following", ["op:instruction_following"]),
    "instruction-following": _e("language_communication", "instruction_following", ["op:instruction_following"]),
    "指令遵循": _e("language_communication", "instruction_following", ["op:instruction_following"]),
    "instruct": _e("language_communication", "instruction_following", ["op:instruction_following"]),
    "prompt recovery": _e("language_communication", "instruction_following", ["op:instruction_following"]),
    "personalization": _e("language_communication", "dialogue_roleplay"),
    "writing": _e("language_communication", "creative_writing"),
    "creativity": _e("language_communication", "creative_writing"),
    "creation": _e("language_communication", "creative_writing"),
    "创作": _e("language_communication", "creative_writing"),
    "writing style transformation": _e("language_communication", "creative_writing"),
    "summarization": _e("language_communication", "summarization"),
    "long_context": _e("language_communication", "long_context_text", ["op:long_context"]),
    "long context": _e("language_communication", "long_context_text", ["op:long_context"]),
    "long-context": _e("language_communication", "long_context_text", ["op:long_context"]),
    "长上下文": _e("language_communication", "long_context_text", ["op:long_context"]),
    "长文本": _e("language_communication", "long_context_text", ["op:long_context"]),
    "needle in a haystack": _e("language_communication", "long_context_text", ["op:long_context"]),
    "memory": _e("language_communication", "long_context_text", ["op:memory"]),
    "spoken text": _e("multimodal_perception", "audio_speech", ["modality:audio"]),

    # ---- multimodal perception
    "multimodal": _e("multimodal_perception", "multimodal_general", ["modality:multimodal"]),
    "多模态": _e("multimodal_perception", "multimodal_general", ["modality:multimodal"]),
    "omni-modal": _e("multimodal_perception", "multimodal_general", ["modality:multimodal"]),
    "multimodal reasoning": _e("multimodal_perception", "cross_modal_reasoning", ["modality:multimodal"]),
    "cross-modal reasoning": _e("multimodal_perception", "cross_modal_reasoning", ["modality:multimodal"]),
    "跨模态推理": _e("multimodal_perception", "cross_modal_reasoning", ["modality:multimodal"]),
    "vision": _e("multimodal_perception", "image_understanding_vqa", ["modality:image"]),
    "视觉": _e("multimodal_perception", "image_understanding_vqa", ["modality:image"]),
    "computer vision": _e("multimodal_perception", "image_understanding_vqa", ["modality:image"]),
    "vision-language": _e("multimodal_perception", "image_understanding_vqa", ["modality:image"]),
    "image": _e("multimodal_perception", "image_understanding_vqa", ["modality:image"]),
    "image_to_text": _e("multimodal_perception", "image_understanding_vqa", ["modality:image"]),
    "image understanding": _e("multimodal_perception", "image_understanding_vqa", ["modality:image"]),
    "图像理解": _e("multimodal_perception", "image_understanding_vqa", ["modality:image"]),
    "vqa": _e("multimodal_perception", "image_understanding_vqa", ["modality:image"]),
    "visual-qa": _e("multimodal_perception", "image_understanding_vqa", ["modality:image"]),
    "avqa": _e("multimodal_perception", "audio_speech", ["modality:audio", "modality:video"]),
    "text-rich image": _e("multimodal_perception", "ocr_document", ["modality:image"]),
    "reasoning-vlm": _e("multimodal_perception", "cross_modal_reasoning", ["modality:image"]),
    "vlm reasoning": _e("multimodal_perception", "cross_modal_reasoning", ["modality:image"]),
    "visual mathematical reasoning": _e("math_logic", "math_general", ["modality:image"]),
    "multi-image math benchmark": _e("math_logic", "math_general", ["modality:image"]),
    "video": _e("multimodal_perception", "video_understanding", ["modality:video"]),
    "视频": _e("multimodal_perception", "video_understanding", ["modality:video"]),
    "video understanding": _e("multimodal_perception", "video_understanding", ["modality:video"]),
    "video-understanding": _e("multimodal_perception", "video_understanding", ["modality:video"]),
    "视频理解": _e("multimodal_perception", "video_understanding", ["modality:video"]),
    "long video understanding": _e("multimodal_perception", "video_understanding", ["modality:video", "op:long_context"]),
    "video reasoning": _e("multimodal_perception", "cross_modal_reasoning", ["modality:video"]),
    "视频推理": _e("multimodal_perception", "cross_modal_reasoning", ["modality:video"]),
    "fine-grained temporal understanding": _e("multimodal_perception", "video_understanding", ["modality:video"]),
    "live streams": _e("multimodal_perception", "video_understanding", ["modality:video"]),
    "视频生成": _e("multimodal_perception", "visual_generation_editing", ["modality:video"]),
    "audio": _e("multimodal_perception", "audio_speech", ["modality:audio"]),
    "audio understanding": _e("multimodal_perception", "audio_speech", ["modality:audio"]),
    "音频理解": _e("multimodal_perception", "audio_speech", ["modality:audio"]),
    "audio-visual": _e("multimodal_perception", "audio_speech", ["modality:audio", "modality:video"]),
    "speech_to_text": _e("multimodal_perception", "audio_speech", ["modality:audio"]),
    "ocr": _e("multimodal_perception", "ocr_document", ["modality:image"]),
    "ocr and document understanding": _e("multimodal_perception", "ocr_document", ["modality:image"]),
    "document_understanding": _e("multimodal_perception", "ocr_document", ["modality:document"]),
    "document content extraction": _e("multimodal_perception", "ocr_document", ["modality:document"]),
    "charts": _e("multimodal_perception", "chart_diagram", ["modality:image"]),
    "visual generation": _e("multimodal_perception", "visual_generation_editing", ["modality:image"]),
    "视觉生成": _e("multimodal_perception", "visual_generation_editing", ["modality:image"]),
    # OpenCompass renders this badge as `Generation` in English, but its Chinese
    # twin on the same 13 records is 语言生成 -- language generation, not visual.
    "generation": _e("language_communication", "creative_writing"),
    "语言生成": _e("language_communication", "creative_writing"),
    "text-to-image": _e("multimodal_perception", "visual_generation_editing", ["modality:image"]),
    "image-generation": _e("multimodal_perception", "visual_generation_editing", ["modality:image"]),
    "image editing": _e("multimodal_perception", "visual_generation_editing", ["modality:image"]),
    "aigc": _e("multimodal_perception", "visual_generation_editing", ["modality:image"]),
    "stereo conversion": _e("multimodal_perception", "visual_generation_editing", ["modality:3d"]),
    "forgery detection": _e("multimodal_perception", "image_understanding_vqa", ["modality:image"]),
    "spatial_reasoning": _e("multimodal_perception", "spatial_3d", ["modality:3d", "op:spatial"]),
    "spatial": _e("multimodal_perception", "spatial_3d", ["op:spatial"]),
    "spatial understanding": _e("multimodal_perception", "spatial_3d", ["op:spatial"]),
    "spatial-understanding": _e("multimodal_perception", "spatial_3d", ["op:spatial"]),
    "空间理解": _e("multimodal_perception", "spatial_3d", ["op:spatial"]),
    "spatial intelligence": _e("multimodal_perception", "spatial_3d", ["op:spatial"]),
    "3d spatial reasoning": _e("multimodal_perception", "spatial_3d", ["modality:3d", "op:spatial"]),
    "3d": _e("multimodal_perception", "spatial_3d", ["modality:3d"]),
    "visual-localization": _e("multimodal_perception", "spatial_3d", ["op:spatial"]),
    "visual place recognition": _e("multimodal_perception", "spatial_3d", ["op:spatial"]),

    # ---- safety & security
    "safety": _e("safety_security", "safety_general", ["op:safety_probe"]),
    "安全": _e("safety_security", "safety_general", ["op:safety_probe"]),
    "safety alignment": _e("safety_security", "harmfulness_alignment", ["op:safety_probe"]),
    "安全对齐": _e("safety_security", "harmfulness_alignment", ["op:safety_probe"]),
    "security": _e("safety_security", "cybersecurity_offensive", ["op:safety_probe"]),
    "jailbreak": _e("safety_security", "jailbreak_robustness", ["op:safety_probe"]),
    "implicit risk": _e("safety_security", "harmfulness_alignment", ["op:safety_probe"]),
    "agentic physical security": _e("safety_security", "cybersecurity_offensive", ["interaction:agentic"]),
    "privacy": _e("safety_security", "privacy", ["op:safety_probe"]),

    # ---- applied verticals
    "healthcare": _e("applied_verticals", "healthcare_medical"),
    "medical": _e("applied_verticals", "healthcare_medical"),
    "health": _e("applied_verticals", "healthcare_medical"),
    "医疗": _e("applied_verticals", "healthcare_medical"),
    "medical imagery": _e("applied_verticals", "healthcare_medical", ["modality:image"]),
    "chinese medicine": _e("applied_verticals", "healthcare_medical"),
    "tcm": _e("applied_verticals", "healthcare_medical"),
    "legal": _e("applied_verticals", "legal"),
    "法律": _e("applied_verticals", "legal"),
    "legal ai": _e("applied_verticals", "legal"),
    "legal benchmark": _e("applied_verticals", "legal"),
    "finance": _e("applied_verticals", "finance_economics"),
    "金融": _e("applied_verticals", "finance_economics"),
    "economics": _e("applied_verticals", "finance_economics"),
    "business": _e("applied_verticals", "business_productivity"),
    "professional": _e("applied_verticals", "business_productivity"),

    # ---- general / composite
    "general": _e("general_composite", "general_capability", [], generic=True),
    "通用": _e("general_composite", "general_capability", [], generic=True),
    "comprehensive capability": _e("general_composite", "general_capability"),
    "综合能力": _e("general_composite", "general_capability"),
    "intelligence-index": _e("general_composite", "aggregate_index"),
    "living benchmark": _e("general_composite", "general_capability", ["op:live_dynamic"]),
    "dynamic benchmarking": _e("general_composite", "general_capability", ["op:live_dynamic"]),

    # ---- Chinese twins of English badges in the same OpenCompass column.
    # Redundant for scoring, kept so a CJK-only tag still resolves and the
    # unmapped-token report stays a real signal rather than translation noise.
    "检索能力": _e("agentic_tool_use", "web_browsing_deep_research", ["op:retrieval_rag"]),
    "指令跟随": _e("language_communication", "instruction_following", ["op:instruction_following"]),
    "ocr与文档理解": _e("multimodal_perception", "ocr_document", ["modality:image"]),
    "科学": _e("science_research", "science_general"),
    "视觉问答": _e("multimodal_perception", "image_understanding_vqa", ["modality:image"]),
    "医学": _e("applied_verticals", "healthcare_medical"),
    "幻觉": _e("knowledge_factuality", "factuality_hallucination"),
    "视觉定位": _e("multimodal_perception", "spatial_3d", ["op:spatial"]),

    # ---- Chinese-only OpenCompass basic_tags, read against each record's card.
    "航运": _e("applied_verticals", "vertical_general"),          # MaritimeBench
    "海运": _e("applied_verticals", "vertical_general"),          # MaritimeBench
    "农业": _e("applied_verticals", "vertical_general"),          # AgMMU
    "生产力工具": _e("applied_verticals", "business_productivity"),  # AIDABench
    "ai数据分析": _e("coding_se", "data_sql"),                     # AIDABench
    "数据可视化": _e("multimodal_perception", "chart_diagram"),      # AIDABench
    "代码生成": _e("coding_se", "code_generation"),
    "代码可视化": _e("coding_se", "code_general"),
    "表格问答": _e("language_communication", "reading_comprehension"),  # TableEval
    "跨语言": _e("language_communication", "multilingual_translation", ["op:multilingual"]),
    "文本嵌入": _e("language_communication", "language_general"),
    "强化学习": _e("science_research", "research_engineering_ml"),
    "fea基准测试": _e("science_research", "physics"),               # finite-element analysis
    "物理保真": _e("science_research", "physics"),                  # GAUGE, world-model realism
    "音频语言模型": _e("multimodal_perception", "audio_speech", ["modality:audio"]),
    "视频评估": _e("multimodal_perception", "video_understanding", ["modality:video"]),
    "图像评估": _e("multimodal_perception", "image_understanding_vqa", ["modality:image"]),
    "系统1": _e("math_logic", "logical_puzzle_reasoning", ["op:reasoning"]),   # S1-Bench
    "快思考": _e("math_logic", "logical_puzzle_reasoning", ["op:reasoning"]),   # S1-Bench
    "深度推理": _e("math_logic", "abstract_reasoning", ["op:reasoning"]),
    "多步推理": _e("math_logic", "logical_puzzle_reasoning", ["op:reasoning"]),
    "空间智能": _e("multimodal_perception", "spatial_3d", ["op:spatial"]),
    "跨视角": _e("multimodal_perception", "spatial_3d", ["op:spatial"]),
    # DOVE measures answer stability under prompt perturbation, not harm.
    "llm敏感性评估": _e("general_composite", "robustness_consistency", ["op:robustness"]),
    # A property of the data, not a capability: facets only, no L1 vote.
    "真实世界数据": _e(None, None, ["op:real_world"]),
}

# --- text patterns ------------------------------------------------------
# (regex, l1, l2, facets, exclude). Applied to name + description; every match
# is recorded with its pattern. `exclude`, when it matches the same text, drops
# the pattern for that record.
#
# A facet asserts something about how the benchmark is run, so a pattern may
# grant one only when the matched phrase names that interaction. A word that
# names a data source (`bnlearn repository`), an application domain (`autonomous
# driving`), or the benchmark's own title (a benchmark called `Shell`) is not
# evidence of an agent loop, and those patterns carry no facet.
TEXT_PATTERNS = [
    # An issue-resolution task is an agent loop; merely naming a repository is
    # not. `bnlearn repository` and `modular codebase` are data and tooling.
    (r"\bswe[- ]?bench|\bpull request|\bgithub issue|\bissue resolution", "coding_se", "swe_repo_issue", ["interaction:agentic"], None),
    (r"\brepositor(y|ies)\b|\bcodebase\b", "coding_se", "swe_repo_issue", [], None),
    (r"\bcodeforces|\bcompetitive programming|\bicpc\b|\bleetcode", "coding_se", "competitive_programming", [], None),
    (r"\bsql\b|\btext[- ]to[- ]sql|\bdatabase quer", "coding_se", "data_sql", [], None),
    (r"\bcode\b|\bcoding\b|\bprogram(ming|s)?\b|\bhumaneval|\bmbpp\b|\bunit test", "coding_se", "code_general", [], None),
    (r"\baime\b|\bhmmt\b|\bimo\b|\bolympiad|\bcompetition math", "math_logic", "competition_math", [], None),
    (r"\btheorem prov|\blean\b|\bcoq\b|\bformal(ised|ized)? math", "math_logic", "formal_theorem_proving", [], None),
    (r"\bmathemat|\bmath\b|\barithmetic|\balgebra|\bgeometry|\bgsm8k", "math_logic", "math_general", [], None),
    (r"\bpuzzle|\blogical? reasoning|\bdeducti|\bsyllogis|\barc[- ]agi", "math_logic", "logical_puzzle_reasoning", [], None),
    (r"\bphysics|\bquantum\b|\bmechanic", "science_research", "physics", [], None),
    (r"\bchemi|\bmolecul|\bcompound", "science_research", "chemistry", [], None),
    (r"\bbiolog|\bgenom|\bprotein|\bclinical trial", "science_research", "biology_life_science", [], None),
    (r"\bscientific\b|\bscience\b|\bresearch paper|\barxiv\b|\bpeer[- ]review", "science_research", "science_general", [], None),
    (r"\bmachine learning engineer|\bml engineer|\bkaggle|\bmodel training", "science_research", "research_engineering_ml", [], None),
    (r"\bfunction[- ]calling\b|\btool call|\btool[- ]use\b|\bapi call", "agentic_tool_use", "tool_function_calling",
     ["interaction:agentic", "op:tool_calling"], r"\bno[- ]tools?\b|\bwithout tools?\b|\btools? disabled"),
    (r"\bcomputer use|\bgui\b|\bdesktop\b|\bos ?world|\bscreenshot", "agentic_tool_use", "computer_gui_use", ["interaction:agentic", "modality:gui"], None),
    (r"\bterminal[- ]bench|\bterminal (task|environment|session)|\bshell (command|script|session)|\bcommand[- ]line\b|\bbash\b",
     "agentic_tool_use", "os_terminal", ["interaction:agentic"], None),
    (r"\bbrows(e|ing)\b|\bweb search|\bdeep research|\bsearch engine", "agentic_tool_use", "web_browsing_deep_research", ["interaction:agentic", "op:retrieval_rag"], None),
    (r"\bagent(ic|s)?\b|\bmulti[- ]step task|\bautonomous agent", "agentic_tool_use", "agent_general",
     ["interaction:agentic"], r"\bautonomous[- ](driving|vehicle)|\bself[- ]driving"),
    (r"\bmedical|\bclinical|\bhealth|\bpatient|\bdiagnos|\bdisease", "applied_verticals", "healthcare_medical", [], None),
    (r"\blegal\b|\blaw\b|\bcourt\b|\bcontract review|\bjuris", "applied_verticals", "legal", [], None),
    (r"\bfinanc|\bbank(ing)?\b|\baccounting|\binvest|\beconomic", "applied_verticals", "finance_economics", [], None),
    (r"\bspreadsheet|\boffice\b|\bslide deck|\bcustomer service|\bworkplace", "applied_verticals", "business_productivity", [], None),
    (r"\bjailbreak|\bred[- ]team|\bharmful\b|\btoxic|\bmisuse\b|\brefusal", "safety_security", "harmfulness_alignment", ["op:safety_probe"], None),
    (r"\bcyber|\bvulnerabilit|\bexploit\b|\bcve\b|\bctf\b|\bpenetration test", "safety_security", "cybersecurity_offensive", ["op:safety_probe"], None),
    (r"\bprivacy|\bpii\b|\bpersonal data", "safety_security", "privacy", ["op:safety_probe"], None),
    (r"\bhallucinat|\bfactual|\bfact[- ]check|\battribut(ion|ed) to sources", "knowledge_factuality", "factuality_hallucination", [], None),
    (r"\bexam\b|\bgaokao|\bcollege entrance|\bcivil service|\bsubject knowledge", "knowledge_factuality", "exam_academic", ["op:examination"], None),
    (r"\bworld knowledge|\btrivia|\bencyclop|\bopen[- ]domain q", "knowledge_factuality", "world_knowledge_qa", [], None),
    (r"\bcommonsense|\bcommon sense", "knowledge_factuality", "commonsense", [], None),
    (r"\bocr\b|\bdocument understanding|\bpdf\b|\bscanned", "multimodal_perception", "ocr_document", ["modality:document"], None),
    (r"\bchart\b|\bdiagram|\bplot\b|\bfigure understanding", "multimodal_perception", "chart_diagram", ["modality:image"], None),
    (r"\bvideo\b|\btemporal understanding", "multimodal_perception", "video_understanding", ["modality:video"], None),
    (r"\baudio\b|\bspeech\b|\bspoken\b|\basr\b", "multimodal_perception", "audio_speech", ["modality:audio"], None),
    (r"\bimage\b|\bvisual\b|\bvision\b|\bvqa\b|\bpicture", "multimodal_perception", "image_understanding_vqa", ["modality:image"], None),
    (r"\bembodied\b|\brobot|\brobotic manipulation|\bnavigation task", "agentic_tool_use", "embodied_agent", ["modality:embodied"], None),
    (r"\btranslat|\bmultilingual|\bcross[- ]lingual|\bacross \d+ languages", "language_communication", "multilingual_translation", ["op:multilingual"], None),
    (r"\binstruction[- ]following|\bformat constraint|\bverifiable instruction", "language_communication", "instruction_following", ["op:instruction_following"], None),
    (r"\bcreative writing|\bstory\b|\bpoem|\bnarrative", "language_communication", "creative_writing", [], None),
    (r"\bsummar(y|ise|ize)", "language_communication", "summarization", [], None),
    (r"\bhuman preference|\belo\b|\barena\b|\bpairwise comparison|\bchatbot", "language_communication", "human_preference_chat", [], None),
    (r"\brole[- ]?play|\bpersona\b|\bdialogue\b|\bconversation", "language_communication", "dialogue_roleplay", [], None),
    (r"\blong[- ]context|\b128k\b|\b1m tokens|\bneedle in a haystack|\bhaystack", "language_communication", "long_context_text", ["op:long_context"], None),
    (r"\breading comprehension|\bcomprehension\b|\bpassage", "language_communication", "reading_comprehension", [], None),
    (r"\baggregate index|\bcomposite (score|index)|\bintelligence index", "general_composite", "aggregate_index", [], None),
]
