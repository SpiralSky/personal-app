# Open-weight email classifiers and labelled email datasets for triage (as of 2026-10-08)

Scope: models and datasets a privacy-sensitive student could run locally (CPU or small GPU) to sort their own mail into 8 categories (action_required, deadline, notice, opportunity, personal, system, newsletter, other) and 4 priorities (urgent, soon, whenever, ignore). Context: Singapore polytechnic inbox, English, about 150 emails a month. Pure spam and phishing detectors are left out.

Research method note: I made about 20 search and fetch calls. Several Hugging Face model cards returned HTTP 401 or only partial README content, so some per-model details (download counts, exact metrics) are missing and are listed under Gaps.

## Q1. Open-weight models trained for email category, intent, priority or action (not spam)

### Takeaway
Only a few small, hobbyist-grade email category classifiers are on Hugging Face. The most relevant is **Ippoboi/mmbert-base-email-classifier**, an ONNX, CPU-friendly mmBERT model with two heads: 6 Gmail-style categories plus an "action required" probability. None has a label set that matches the user's 8+4 scheme. None reports solid, independently verifiable metrics. All are trained on small (about 2k) personal or synthetic datasets. Treat them as starting points or baselines, not as ready-made solutions.

### Cited Findings
**Ippoboi/mmbert-base-email-classifier (v9)**
- Dual-head mmBERT-base classifier for "multilingual email category + action prediction, optimized for on-device inference with ONNX Runtime" — [HF model card (search snippet)](https://huggingface.co/Ippoboi/mmbert-base-email-classifier)
- Six categories: PERSONAL, NEWSLETTER, PROMOTIONAL, TRANSACTION, ALERT, SOCIAL. Outputs `category_probs` (Float32[6] softmax) and `action_prob` (Float32[1] sigmoid, "action required"), with a calibrated threshold of 0.525 — [HF model card (search snippet)](https://huggingface.co/Ippoboi/mmbert-base-email-classifier)
- v9 input changes: sender is fed to the model, link domains are kept, boilerplate footers are stripped, and truncation is token-budgeted — [HF model card (search snippet)](https://huggingface.co/Ippoboi/mmbert-base-email-classifier)
- The same author has related repos: `Ippoboi/minilmail-classifier` (a MiniLM variant with example.py) and `Ippoboi/gmail-classifier` — [HF](https://huggingface.co/Ippoboi/minilmail-classifier/blob/main/example.py)
- The `Ippoboi/gmail-classifier` README describes a google/flan-t5-small model (about 80M params, 357 MB, Apache-2.0) with labels PERSONAL, NEWSLETTER, TRANSACTION, ALERT, SOCIAL plus an action flag. It was trained on 2,043 train / 256 val / 255 test examples from anonymised personal Gmail inboxes (English and French), annotated by hand. The card reports about 79 ms latency on an iPhone CPU and max sequence length 512. Last updated about 7 months before fetch. It reports no accuracy figure. The card's title says "Email Summarizer T5", which is inconsistent with its content — [README](https://huggingface.co/Ippoboi/gmail-classifier/blob/main/README.md)

**imnim/multi-label-email-classifier**
- LoRA/PEFT adapter on meta-llama/Llama-3.1-8B-Instruct, MIT licence. Multi-label over 10 classes: Business, Personal, Promotions, Customer Support, Job Application, Finance & Bills, Events & Invitations, Travel & Bookings, Reminders, Newsletters. Trained on a synthetic dataset of 2,105 emails on a Kaggle P100. No metrics reported. Dataset timestamp is June 2025. 13 downloads last month — [HF model card](https://huggingface.co/imnim/multi-label-email-classifier)
- It is an 8B base, so it needs a GPU or a quantised GGUF to run locally. Nothing indicates a published quantised version.

**byinab/custom-email-classifier**
- DistilBertForSequenceClassification (about 66M params) with the same 10-class label set as imnim (Business, Customer Support, Events & Invitations, Finance & Bills, Job Application, Newsletters, Personal, Promotions, Reminders, Travel & Bookings) — [config.json](https://huggingface.co/byinab/custom-email-classifier/blob/main/config.json). Licence and metrics were not retrieved.

**Other small or hobby models found (details unverified)**
- `i-dhilip/qwen25-email-clf`: Qwen2.5-based email classifier. The listing mentions sorting into 'work', 'personal', 'promotions', 'social' — [featherless.ai listing](https://featherless.ai/models/i-dhilip/qwen25-email-clf)
- `curriculo-tech/onnx-email-gate`: "multilingual KEEP/DROP email prefilter" in ONNX — [HF](https://huggingface.co/curriculo-tech/onnx-email-gate)
- `adaptive-classifier/email-priority`: a priority classifier repo — [HF](https://huggingface.co/adaptive-classifier/email-priority/tree/main)
- `FlowRank` "mailSort" text-classification model and "labeled_emails" dataset — [HF](https://huggingface.co/FlowRank/models)
- `lewispons/Email-classifier-v2`: sentence-transformers style, with a Pooling folder — [HF](https://huggingface.co/lewispons/Email-classifier-v2/tree/main/1_Pooling)
- `mattohan/job-tracker-email-classifier`: job-application email classifier — [HF](https://huggingface.co/mattohan/job-tracker-email-classifier/blob/main/tokenizer.json)

**Research (non-open) models for related tasks**
- Yahoo Mail human-vs-machine email classifier (AAAI'22): an ensemble of four CNNs (content, sender, action, salutation). Adjusted recall went from 70.5% to 78.8% and precision from 94.7% to 96.0%, beating a BERT baseline. Proprietary data, no weights released — [arXiv 2112.07742](https://arxiv.org/abs/2112.07742)
- Microsoft email intent detection with weak supervision from user actions (SIGIR 2020). User interaction logs serve as noisy labels (e.g. scheduling a meeting after a request) and are combined with clean labels through self-paced learning. No public weights — [arXiv 2005.13084](https://arxiv.org/abs/2005.13084)

### Inferences
- Label mapping to the user's scheme:
  - Ippoboi's NEWSLETTER→newsletter, PERSONAL→personal, ALERT/TRANSACTION→system, PROMOTIONAL/SOCIAL→other or newsletter (LinkedIn alerts would likely land in SOCIAL or ALERT).
  - Its `action_prob` approximates action_required.
  - Nothing maps to deadline, notice (staff announcements), opportunity, or any priority level.
  - The 10-class imnim/byinab set maps "Events & Invitations" and "Job Application" loosely to opportunity, "Reminders" loosely to deadline, and "Newsletters" to newsletter.
- Of the found models, only the Ippoboi ONNX mmBERT model is a realistic CPU option out of the box. Its action head is the closest existing thing to an "actionable email" detector.
- Every model found is a single-author project trained on about 2k emails, often synthetic. None has independent evaluation, so expect a domain-shift drop on polytechnic and LMS mail.

### Gaps
- I could not retrieve accuracy/F1, licence, parameter count or download counts for Ippoboi/mmbert-base-email-classifier (model card returned HTTP 401 to the fetcher). mmBERT-base is about 300M params according to the Laya notes below, which is a related but separate source.
- I found no open model for request/commitment detection, reply-needed prediction, or deadline extraction specific to email with public weights.
- I could not verify the licence or metrics for byinab, i-dhilip, curriculo-tech, adaptive-classifier, FlowRank or lewispons models.

## Q2. Zero-shot / NLI classifiers and "decision models" usable on email; small models vs LLMs

### Takeaway
General zero-shot encoders can classify emails into arbitrary labels without email-specific training, and all run on CPU. These include MoritzLaurer's DeBERTa-v3 and ModernBERT zeroshot-v2.0 NLI models, GLiClass, and the new September 2026 wave of open "decision models" (Laya, GLiNER2.5-Decide). I found no email-triage-specific benchmark for them. The only email numbers are Laya's spam, phishing and support-ticket results. A single comparison (not independently verified) found a fine-tuned encoder beating an LLM pipeline on corporate email intent.

### Cited Findings
**NLI zero-shot classifiers**
- MoritzLaurer zeroshot collection, includes deberta-v3-base/large-zeroshot-v2.0 and deberta-v3-base-zeroshot-v1.1-all-33. Works with HF ZeroShotClassificationPipeline. v2.0 "can run on both GPUs and CPUs" — [HF collection](https://huggingface.co/collections/MoritzLaurer/zeroshot-classifiers); [deberta-v3-large-zeroshot-v1](https://huggingface.co/MoritzLaurer/deberta-v3-large-zeroshot-v1); method paper "Building Efficient Universal Classifiers with NLI" — [arXiv 2312.17543](https://arxiv.org/pdf/2312.17543)
- ModernBERT-large-zeroshot-v2.0: fine-tuned from answerdotai/ModernBERT-large, noted for speed and memory efficiency compared with DeBERTa-v3 — [PromptLayer model page](https://www.promptlayer.com/models/modernbert-large-zeroshot-v20)
- GLiClass (knowledgator/gliclass-modern-large-v3.0): "generalist and lightweight model for sequence classification" — [HF](https://huggingface.co/knowledgator/gliclass-modern-large-v3.0)

**Laya (Convai Innovations, September 2026)**
- Open-source, Apache-2.0. "Weights, code, benchmark harness, and training notebook are all public." HF id `convaiinnovations/laya` — [mer.vin](https://mer.vin/news/laya-the-33ms-open-source-decision-model-beating-jev/)
- Three checkpoints:
  - laya: ModernBERT-large, 421M, 512 context
  - laya-multilingual: mmBERT-base, 322M, 1024 context
  - laya-typed-decisions: ModernBERT-large, 421M, 1024 context
  - [mer.vin](https://mer.vin/news/laya-the-33ms-open-source-decision-model-beating-jev/)
- Takes text plus typed questions (choice / score / noul yes-no) and returns calibrated probabilities in about 33 ms on one GPU. Training method "RLCD" uses a strictly proper scoring rule as reward — [mer.vin](https://mer.vin/news/laya-the-33ms-open-source-decision-model-beating-jev/)
- Email-related results:
  - Support-ticket routing (10-way): 0.522 accuracy
  - Email spam: 0.993 accuracy, ECE 0.013
  - Phishing: 0.980 accuracy, ECE 0.012
  - vs Jev: typed-decisions 0.766 vs 0.727; AG News 0.950 vs 0.910
  - [mer.vin](https://mer.vin/news/laya-the-33ms-open-source-decision-model-beating-jev/)
- Calibration caveat: the models "ship over-confident" and need temperature fitting before deployment. Base-model ECE went from 0.466 to 0.081 after fitting — [mer.vin](https://mer.vin/news/laya-the-33ms-open-source-decision-model-beating-jev/)
- CPU latency is 193–464 ms per request — [mer.vin](https://mer.vin/news/laya-the-33ms-open-source-decision-model-beating-jev/)

**GLiNER2.5-Decide (Fastino Labs, 24 Sep 2026)**
- 340M open-weight encoder, Apache-2.0, English only. Jointly decodes user-defined typed questions and rules into structured decisions with confidence — [soniqo.audio](https://soniqo.audio/blog/gliner-decide-vs-jev)
- Exact-match accuracy on fastino/fast-decisions (17 domains × 300 held-out examples):

  | Model | Accuracy |
  |---|---|
  | GLiNER2.5-Decide 340M | 60.2% |
  | GLiNER2.5-Decide-1B | 59.6% |
  | JevK5 (open reproduction of Jev) | 57.6% |
  | GLiNER2.5-multi-Decide 287M | 56.7% |
  | SemIf (Qwen3.5-4B) | 56.4% |
  | GLiFormer large-v1 | 49.0% |
  | Laya Router | 46.6% |

  The article does not name the domains, and no email domain is identified — [soniqo.audio](https://soniqo.audio/blog/gliner-decide-vs-jev)
- MLX INT8 port `aufklarer/GLiNER2.5-Decide-340M-MLX-8bit`: 7.6 ms routing, 0.85 GB memory on Apple M5 Pro — [soniqo.audio](https://soniqo.audio/blog/gliner-decide-vs-jev)

**Small models vs LLMs on email**
- A corporate email intent study reported a fine-tuned XLM-RoBERTa encoder at F1 0.78 against an LLM pipeline at F1 0.73, with "nearly half the false positives" and zero per-call cost — [INJOIT article (search-result summary only, not fetched)](https://injoit.ru/index.php/j1/article/view/2576)
- For spam, zero-shot Flan-T5 reached 90% F1 and GPT-4 95% F1 (on summaries) — [arXiv 2405.15936](https://arxiv.org/abs/2405.15936v1)
- Sales-engagement email classification: transfer learning evaluated at scale — [arXiv 1905.01971](https://arxiv.org/pdf/1905.01971)

### Inferences
- For 150 emails a month, CPU latency of 200–500 ms per email (Laya) or similar for DeBERTa-large NLI is negligible. Throughput is not the constraint; label quality is.
- Typed-question decision models (Laya, GLiNER2.5-Decide) fit the user's schema naturally: one `choice` over 8 categories plus one `score` or `choice` over 4 priorities, both in one pass. Their 10-way ticket routing score (Laya 0.522) and roughly 47–60% exact-match on mixed domains suggest zero-shot accuracy on a custom 8-way scheme will be mediocre without fine-tuning or few-shot adaptation.
- NLI zero-shot needs good label descriptions ("This email asks me to do something" rather than "action_required"). Priority is hard for NLI because it depends on dates and the sender.

### Gaps
- No published benchmark of NLI zero-shot or decision models on email category or priority triage.
- I did not fetch the INJOIT paper itself. The 0.78 vs 0.73 figure comes from a search summary.

## Q3. Public labelled email datasets

### Takeaway
No public dataset matches the user's 8-category + 4-priority scheme. The academic intent and action corpora are built on Enron (public) or Avocado (LDC licence, not free). Their labels are sentence-level request/commitment, not inbox categories. The Hugging Face category and priority datasets are small and mostly LLM-synthetic. The most practical path is to label about 300–1,000 of the user's own emails. Synthetic sets (darshandugar, imnim's 2,105, infinite-dataset-hub) can serve as weak pre-training data.

### Cited Findings
**Enron and Avocado corpora**
- Enron Email Dataset, about 500,000 emails, used for actionable-phrase detection — [arXiv 2210.16841](https://arxiv.org/pdf/2210.16841)
- Request-for-Action / Commitment-to-Act annotation on Enron (Macquarie). Inter-annotator agreement κ = 0.78 for requests, κ = 0.54 for commitments — [Macquarie](https://researchers.mq.edu.au/en/publications/can-requests-for-action-and-commitments-to-act-be-reliably-identi/)
- Email intent categories (information exchange, task management, scheduling, social). The SIGIR'19 work focuses on request information, schedule meeting and promise action — [Wang et al. SIGIR19 PDF](https://microsoft.com:443/en-us/research/uploads/prod/2019/05/Wang_SIGIR19.pdf)
- Smart To-Do: automatic to-do generation from emails — [arXiv 2005.06282](https://arxiv.org/pdf/2005.06282)
- Detecting Action-Items in E-mail (Microsoft Research) — [MSR](https://www.microsoft.com/en-us/research/publication/detecting-action-items-e-mail/)
- Avocado Research Email Collection, LDC2015T03. Requires an LDC Individual or Organization licence agreement — [LDC catalog](https://catalog.ldc.upenn.edu/LDC2015T03)
- EmailSum (ACL 2021): human short (<30 words) and long (<100 words) summaries of 2,549 Avocado threads (3–10 emails each) — [arXiv 2107.14691](https://arxiv.org/pdf/2107.14691)
- AESLC: Enron email subject-line generation dataset on HF/TFDS — [TFDS catalog](https://tensorflow.org/datasets/community_catalog/huggingface/aeslc)

**Hugging Face category and priority datasets**
- infinite-dataset-hub/EmailPriorityDetection: synthetic corporate emails labelled High/Medium/Low priority, CSV — [HF](https://huggingface.co/datasets/infinite-dataset-hub/EmailPriorityDetection). A sibling set, EmployeePriorityEmails, also exists — [HF](https://huggingface.co/datasets/infinite-dataset-hub/EmployeePriorityEmails/tree/main)
- vedaantp/email-priority: CSV with train, validation and test splits — [HF](https://huggingface.co/datasets/vedaantp/email-priority/tree/main)
- darshandugar/Email-Classification-Artificial-Generated: synthetic, MIT licence — [HF README](https://huggingface.co/datasets/darshandugar/Email-Classification-Artificial-Generated/blob/main/README.md)
- amitraheja82 Market_Mail_Synthetic_DataSet(1) — [HF](https://huggingface.co/amitraheja82)
- FlowRank labeled_emails — [HF](https://huggingface.co/FlowRank/models)
- imnim's training set: 2,105 synthetic emails over 10 categories — [HF model card](https://huggingface.co/imnim/multi-label-email-classifier)
- An OpenEnv email triage environment classifies emails as urgent, normal or spam, assigns priority ranks, and drafts replies — [alphaneural listing](https://app.alphaneural.io/assets/Heyabhi/openenv)

### Inferences
- Label-mapping notes:
  - EmailPriorityDetection's High/Medium/Low maps roughly to urgent/soon/whenever. "ignore" has no equivalent.
  - Request/commitment corpora map to action_required only.
  - None covers notice, opportunity or system in a polytechnic or LMS sense.
- Enron and Avocado are early-2000s corporate mail with no newsletters or LMS-style notifications, so they transfer poorly to a 2026 student inbox.
- infinite-dataset-hub sets are LLM-generated and typically small. Their quality is unknown.

### Gaps
- I could not confirm the sizes or licences of vedaantp/email-priority, EmailPriorityDetection, FlowRank or the Market_Mail sets.
- I found no public Gmail-tab-style (Primary/Promotions/Social/Updates) labelled corpus of real email, and no public "Smart Reply" corpus. Google's data was never released, as far as I know (unverified).
- I did not determine whether the Enron request/commitment annotations or the Wang et al. intent labels are downloadable.

## Q4. 2025–2026 decision models (Jev and similar) and email routing results

### Takeaway
Jev (TypeSafe AI) is a closed, hosted-API decision model released in early access on 15 Sep 2026, so it is unsuitable for local or private use. Within about 10 days, several open alternatives appeared: Laya, Kev, Von, Tev1-4B, GLiNER2.5-Decide, plus the open reproductions JevK5 and SemIf seen in benchmarks. None has published email category or priority triage results. Laya reports spam, phishing and 10-way ticket routing. "NanoJev" was not found.

### Cited Findings
**Jev (TypeSafe AI)**
- Released 15 Sep 2026 as TypeSafe's first "System One" model. It takes text or structured state plus predefined typed questions and returns Choice/Score/Noul answers with probability distributions and confidence in one parallel pass — [aimlapi](https://aimlapi.com/blog/what-is-jev); [composio](https://composio.dev/content/typesafe-jev-guide-and-best-practical-usecases)
- "Closed, hosted API only". Pricing is $0.0578 per 1M input tokens (AI/ML API) or $0.042 (OpenRouter). 32K context, up to 255 options per choice — [aimlapi](https://aimlapi.com/blog/what-is-jev)
- Benchmarks:
  - Banking77 intent routing: Jev 78.3% vs Claude Opus 5.5 85.7%
  - TweetEval moderation: F1 0.696, best of six models
  - HelpSteer2 rating: correlation 0.394, lowest of six
  - 6–18× faster than LLMs on the server
  - At confidence ≥0.9 it was right 94–96% of the time
  - [aimlapi](https://aimlapi.com/blog/what-is-jev)

**Open alternatives**
- Laya (Convai, 18 Sep 2026, Apache-2.0, 421M); Kev (Jared Palmer, Apache-2.0, 0.8B–9B); Von (Victor Panisa, Apache-2.0, 395M); Tev1-4B (Together AI, 23 Sep 2026, open weights, "$17 to train"); GLiNER2.5-Decide (Fastino, 24 Sep 2026, Apache-2.0, 340M) — [aimlapi](https://aimlapi.com/blog/what-is-jev)
- JevK5 is described as an "open reproduction" of Jev. SemIf is listed as built on Qwen3.5-4B — [soniqo.audio](https://soniqo.audio/blog/gliner-decide-vs-jev)

### Inferences
- For a privacy-sensitive local setup, the candidates are Laya (CPU-capable, calibrated after temperature fitting, ModernBERT-large) and GLiNER2.5-Decide (340M, English, the highest mixed-domain accuracy reported). Both are a few weeks old, so their maintenance track record is unknown.
- These are very new, mostly vendor or blog-reported numbers. Treat them as preliminary.

### Gaps
- NanoJev: no source found. It may not exist or may be mis-named.
- Kev, Von and Tev1-4B: no email-specific results or HF ids found.
- No independent (third-party, peer-reviewed) evaluation of any decision model on email triage.
- InfoQ's Jev article returned HTTP 405 and was not read.

## Q5. Practical findings: data needed, fine-tuned encoders vs zero-shot LLMs, calibration

### Takeaway
The available evidence is thin but consistent. Small fine-tuned encoders trained on about 2k labelled emails are the norm for hobby email classifiers, and a fine-tuned encoder beat an LLM pipeline on corporate email intent. Calibration is not automatic: even the "calibrated" Laya needs temperature scaling. Requests are easier to label consistently than commitments, and by extension than fuzzy notions like priority.

### Cited Findings
- Existing personal-email classifiers were trained on about 2k labels: 2,043 human-labelled (Ippoboi T5) and 2,105 synthetic (imnim) — [Ippoboi README](https://huggingface.co/Ippoboi/gmail-classifier/blob/main/README.md); [imnim](https://huggingface.co/imnim/multi-label-email-classifier)
- Fine-tuned XLM-R F1 0.78 vs LLM pipeline 0.73 on email intent — [INJOIT (summary only)](https://injoit.ru/index.php/j1/article/view/2576)
- Annotator agreement κ = 0.78 (requests) vs 0.54 (commitments) — [Macquarie](https://researchers.mq.edu.au/en/publications/can-requests-for-action-and-commitments-to-act-be-reliably-identi/)
- Weak supervision from user actions can compensate for scarce clean labels — [arXiv 2005.13084](https://arxiv.org/abs/2005.13084)
- Laya ECE fell from 0.466 to 0.081 after temperature fitting. Jev was 94–96% correct at confidence ≥0.9 — [mer.vin](https://mer.vin/news/laya-the-33ms-open-source-decision-model-beating-jev/); [aimlapi](https://aimlapi.com/blog/what-is-jev)
- Ippoboi's action head ships a tuned threshold (0.525), which implies threshold calibration on validation data — [HF](https://huggingface.co/Ippoboi/mmbert-base-email-classifier)

### Inferences
- At about 150 emails a month, a year of mail is about 1,800 emails, the same order as the existing hobby training sets. Labelling a few hundred, bootstrapped with zero-shot or LLM pre-labels, is realistic.
- A plausible pipeline:
  - zero-shot or decision model, or a local LLM, to pre-label
  - user corrects the labels
  - fine-tune a small encoder (mmBERT, ModernBERT or DeBERTa-base) with two heads
  - temperature-scale on a held-out set
- Rules on sender domain will likely handle "system" (LMS) and "newsletter" (LinkedIn) better than any model.
- Priority (urgent/soon) depends on dates in the body relative to today. A classifier alone will not capture that well, so pair it with deadline/date extraction.

### Gaps
- I found no published learning curve (accuracy vs number of labels) specific to email triage.
- I found no study comparing calibration of fine-tuned email classifiers against zero-shot LLMs.
