# PropFlip - Multi-Agent Real Estate Wholesale Pipeline

A Band.ai-powered system for automated real estate deal sourcing, analysis, and coordination with human oversight.

## Description

PropFlip automates the real estate wholesale process using 5 specialized Band agents that communicate through chat rooms to move deals from discovery to buyer matching. The system implements risk-tiered human approval gates to ensure proper oversight of external communications and financial decisions.

**Core Workflow:**
1. **DiscoveryAgent** ✅ - Scans distressed properties, calculates investment potential using 70% rule
2. **VerificationAgent** ✅ - Validates title chains, checks liens, ensures deal feasibility  
3. **NegotiationAgent** ✅ - Contacts sellers, negotiates terms, structures offers
4. **MatchingAgent** 🔄 - Connects completed deals with cash buyers from database
5. **OrchestratorAgent** 🔄 - Coordinates workflow, manages deal lifecycle

**Human Oversight Model:**
- **Tier 0** (Read-only): Auto-proceed, audit only
- **Tier 1** (Internal): Auto-proceed, notify in chat room  
- **Tier 2** (External contact): Block until human approval
- **Tier 3** (Contracts/money): Hard stop, manual handling required

Each agent integrates the same HumanGate toolset for consistent risk management and audit trails.

## Implementation Status

### ✅ Completed Agents

- **HumanGate Toolset**: Risk-tiered approval system with console/Telegram channels
- **DiscoveryAgent**: Real estate sourcing with 8 data sources (Zillow, Redfin, etc.)
- **VerificationAgent**: Title/lien verification using HasData API  
- **NegotiationAgent**: Seller outreach via SendGrid email + Twilio SMS

### 🔄 In Development

- **MatchingAgent**: Cash buyer matching and disposition
- **OrchestratorAgent**: Workflow coordination and chat room management

## Agent Implementations

### HumanGate Toolset ✅

HumanGate is **not a separate Band agent** - it's a **shared toolset** that all PropFlip agents import and use for human oversight.

#### Architecture

```python
# Each PropFlip agent imports HumanGate tools
from humangate import HumanGate, build_custom_section

gate = HumanGate.from_env()
tools = [
    gate.report_to_owner,    # Report events to human with risk tier
    gate.request_approval,   # Block on tier 2 actions until approved  
    gate.log_event          # Append-only audit trail
] + agent_specific_tools

adapter = LangGraphAdapter(
    tools=tools,
    custom_section=build_custom_section(agent_persona)  # Injects gate rules
)
```

#### Risk Tier Logic

| Tier | Examples | Behavior |
|------|----------|----------|
| **0** | Property research, ARV calculation | Auto-proceed, audit log only |
| **1** | Draft offers, deal scoring | Auto-proceed, post to Band chat room |
| **2** | Send email/SMS to seller/buyer | **Wait for human approval** |
| **3** | Contract execution, money transfer | **Hard stop** - manual handling |

### DiscoveryAgent ✅

**Purpose**: Find and score distressed investment properties

**Data Sources**: 8 real estate platforms via BrightData MCP + HasData API
- Zillow, Redfin, Realtor.com, Foreclosure.com, Auction.com, etc.

**Key Features**:
- 70% rule calculation for maximum offers
- Distress signal detection (foreclosure, divorce, probate)
- Deal scoring algorithm (0-100 scale)
- Only hands off deals scoring >60 to VerificationAgent

**Risk Tiers**: 0-1 (read-only analysis, no external contact)

### VerificationAgent ✅  

**Purpose**: Due diligence on title, liens, and legal status

**Data Sources**: HasData API for property records + public records

**Key Features**:
- Title chain verification and ownership confirmation
- Lien search (tax, mechanic's, judgment, HOA liens)
- Mortgage balance estimation and payoff calculations  
- Bankruptcy check for legal transaction ability
- Verdict system: CLEAR → proceed | REVIEW → human oversight | DECLINE → abandon

**Risk Tiers**: 0-2 (mostly analysis, tier 2 for complex title issues)

### NegotiationAgent ✅

**Purpose**: Contact sellers and negotiate wholesale purchase contracts

**Outreach Channels**: 
- SendGrid email service (CAN-SPAM compliant)
- Twilio SMS service (TCPA compliant with opt-out)

**Key Features**:
- Skip tracing for seller contact information
- Seller psychology profiling (distressed vs investor vs inherited)
- Multi-channel outreach sequences (email + SMS)
- Assignment contract structuring for wholesale deals
- **Every seller contact requires tier 2 human approval**

**Risk Tiers**: 2-3 (all external contact gated, contracts = hard stop)

### Integration Flow

```
DiscoveryAgent → finds deals scoring >60 →
@VerificationAgent → verifies title/liens → verdict CLEAR →  
@NegotiationAgent → gets approval → contacts seller → structures offers
```

### Approval Channels

- **Console**: Always available, blocking `input()` prompts
- **Telegram**: Optional, responds to `/approve` and `/reject` commands
- **Mock**: Test-only, primed responses for automated testing

## Getting Started

### Prerequisites

1. **API Keys Required**:
   - AIML API key (for LLM)
   - HasData API key (property data)
   - BrightData account (web scraping)
   - SendGrid API key (email outreach)
   - Twilio account (SMS outreach)

2. **Band.ai Account**:
   - Register agents at app.band.ai
   - Get agent IDs and API keys for each agent

### Installation

```bash
# Clone repository
git clone <repo-url>
cd propflip

# Install dependencies  
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your API keys

# Update agent configuration
# Edit agent_config.yaml with your Band agent IDs
```

### Running Agents

```bash
# Run each agent in separate terminals
python main_discovery.py      # DiscoveryAgent
python main_verification.py   # VerificationAgent (when implemented)
python main_negotiation.py    # NegotiationAgent
```

### Testing

```bash
# Run test suite
python -m pytest tests/ -v

# Test individual agents
python -m pytest tests/test_discovery_agent.py -v
python -m pytest tests/test_negotiation_agent.py -v
```

## Architecture

PropFlip follows Band.ai's multi-agent architecture where:

1. **Each agent runs independently** with its own WebSocket connection
2. **Agents communicate via @mentions** in shared Band chat rooms
3. **Human oversight is embedded** in each agent via HumanGate tools
4. **Risk tiers ensure appropriate approval** for increasingly consequential actions
5. **Shared audit trail** maintains complete deal history across all agents

This design ensures scalability, reliability, and proper human oversight while automating the wholesale real estate deal pipeline.