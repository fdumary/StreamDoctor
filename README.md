# StreamDoctor

StreamDoctor is an AI-supported stream-health assessment tool that turns community observations into understandable, trust-aware insights. It treats a stream like a patient: volunteers report its symptoms, AI provides a second opinion, and the system explains how healthy the stream appears and how much its data can be trusted.

## Why StreamDoctor

Community volunteers can observe streams more frequently and across more locations than most agencies. However, inconsistent terminology, incomplete observations, conflicting photos, and a lack of data-quality signals can make those reports difficult to use.

StreamDoctor addresses this gap by:

- guiding contributors through clear, plain-language observations;
- checking reports for plausibility and internal consistency;
- making AI suggestions reviewable rather than allowing AI to decide alone;
- showing why each report is trusted or flagged; and
- translating trusted observations into practical stream-health guidance.

## Key features

### Guided stream check-up

A simple workflow collects observations about:

- water clarity;
- smell;
- flow;
- foam;
- visible wildlife; and
- a supporting photo.

Tap-to-explain guidance helps contributors understand unfamiliar ecological terms. The observation flow is based on the inputs used by the OneAquaHealth Citizen Science App.

### Explainable AI second opinion

AI reviews the submitted photo and suggests observations such as high turbidity or possible foam, along with its confidence and supporting explanation. Contributors can accept, edit, or reject each suggestion. AI is an assistant, not the final decision-maker.

### Plausibility and consistency checks

Rules identify impossible or contradictory entries, such as:

- an implausible pH value for the reported setting;
- a species reported outside its expected season; or
- a photo that appears clear when the notes describe brown water.

### Explainable trust score

Each report receives a trust score based on four signals:

1. agreement between the AI photo assessment and the contributor's notes;
2. plausibility checks;
3. agreement with nearby observations; and
4. the contributor's reporting history.

The score includes the reasons behind it. Low-trust observations are routed for expert review instead of being silently discarded.

### Trust Lens

The Trust Lens compares a stream-health result with and without trust filtering, making it clear how data quality affects the conclusion.

### Audience-specific diagnosis cards

Trusted observations are summarized as a green, yellow, or red stream-health status:

- **Citizens and families:** practical safety guidance, such as whether wading should be avoided after heavy rain.
- **Researchers:** trends, anomalies, and data-quality context.
- **City planners and water managers:** hotspots and likely contributing causes.

### FHIR interoperability

Verified reports can be represented as FHIR `Observation` and `DiagnosticReport` resources and checked with a FHIR validator such as HAPI FHIR. This supports connections between environmental monitoring and public-health systems through the One Health perspective, where water, animal, and human health are linked.

## Who it helps

- **Volunteers and teachers:** an accessible way to collect observations with immediate, understandable feedback.
- **Researchers:** community data with visible quality and confidence signals.
- **City planners and water managers:** earlier warnings and clearer geographic hotspots.
- **Families and pet owners:** practical information about stream safety.
- **Streams and wildlife:** problems can be identified sooner, when intervention may be easier.

## Data and responsible use

StreamDoctor uses the OneAquaHealth observation fields, openly licensed and credited imagery, and synthetic cases for validation. It is intended to support environmental observation and prioritization, not replace scientific sampling, expert review, or official public-health guidance.
