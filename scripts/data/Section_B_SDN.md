# Section B: Software-Defined Networking (SDN) — Questions 9–25

## Overview

Software-Defined Networking (SDN) is one of the most transformative ideas in modern networking. Traditional networks have "brains" (control plane) embedded in every switch and router — like having a separate GPS in every car. SDN **removes the brain from individual devices** and puts one big brain (the **controller**) in charge of the whole network — like having a central air traffic control tower directing all planes.

This section covers SDN architecture, APIs, OpenFlow protocol, controller placement, scalability, and the P4 programming language.

---

## Key Concepts

### The Core Idea of SDN
- **Traditional Network:** Each device (switch/router) makes its own forwarding decisions using distributed protocols (OSPF, STP, BGP). Control plane + data plane are **coupled** in every device.
- **SDN:** The control plane is **separated** from the data plane and **centralized** in a software controller. Switches become "dumb" forwarding devices that follow instructions.

### Three-Layer SDN Architecture
```
┌──────────────────────────────────────────┐
│    APPLICATION LAYER                      │
│    (Firewall, Load Balancer, Monitor)     │
├────────── Northbound API (REST) ─────────┤
│    CONTROL LAYER                          │
│    (SDN Controller: ONOS, ODL, Ryu)      │
├────────── Southbound API (OpenFlow) ─────┤
│    INFRASTRUCTURE LAYER                   │
│    (Switches, Routers — OpenFlow-enabled) │
└──────────────────────────────────────────┘
```

---

## Questions & Answers

---

### Question 9: SDN Architecture — Traditional vs SDN

#### Traditional Network Architecture

**How it works:** Every switch/router has its own control plane (routing protocols like OSPF, BGP) and data plane (forwarding table). They learn routes from neighbors and make independent decisions.

**Analogy:** Every car has its own GPS — each driver independently decides their route. If road conditions change, every GPS must figure it out separately.

**Problems:**
- Configuration is **per-device** (CLI commands on each box)
- No **global view** of the network
- Slow to adapt to changes
- **Vendor lock-in** (Cisco, Juniper each have proprietary CLIs)

#### SDN Architecture

**How it works:** One centralized controller has a **global view** of the entire network. It computes paths and pushes forwarding rules to switches.

**Analogy:** Air traffic control tower directs all planes. Each plane (switch) follows instructions from the tower (controller).

| Layer | What It Contains | What It Does |
|-------|-----------------|-------------|
| **Application Layer** | Network apps (firewall, load balancer, monitoring) | Uses NBI to program the controller |
| **Control Layer** | SDN Controller (ONOS, ODL, Ryu, Floodlight) | Makes all forwarding decisions; maintains global network view |
| **Infrastructure Layer** | OpenFlow switches and routers | Forwards packets based on rules from the controller |

#### Comparison Table

| Feature | Traditional Network | SDN |
|---------|-------------------|-----|
| Control/Data Plane | Coupled in each device | Decoupled; centralized controller |
| Configuration | CLI per device, manual | Programmable via API, automated |
| Network View | Per-device, distributed | Global, centralized |
| Protocols | OSPF, STP, BGP (distributed) | Centralized decision + OpenFlow |
| Vendor Lock-in | Proprietary firmware | Open standards, vendor-neutral |
| Flexibility | Hardware-dependent, slow changes | Software-driven, rapid innovation |
| Scalability | Per-device processing | Controller handles scale; can cluster |
| Cost | Expensive proprietary gear | Commodity hardware + software |
| Troubleshooting | Device-by-device | Centralized logging and visibility |

---

### Question 10: SDN APIs (NB, SB, EB, WB)

SDN has **four types of interfaces** (APIs) — think of them as the communication channels between different parts of the SDN ecosystem.

| Interface | Full Name | Location | Protocols/Tech | Purpose |
|-----------|-----------|----------|---------------|---------|
| **SBI** | Southbound Interface | Controller ↔ Switches | OpenFlow, NETCONF, OVSDB, P4Runtime, ForCES | Program flow tables, configure switches |
| **NBI** | Northbound Interface | Controller ↔ Applications | REST API, gRPC, Java API | Apps request network services (topology, stats, flow rules) |
| **EBI** | East-West (East-Bound) Interface | Controller ↔ Controller | Custom protocols (ONOS Raft, ODL Akka) | Synchronize state between distributed controllers |
| **WBI** | Westbound Interface | Controller ↔ Legacy Devices | SNMP, CLI, SSH, NETCONF | Manage non-SDN (legacy) devices |

**Analogy:**
- **SBI** = The boss (controller) giving orders DOWN to workers (switches)
- **NBI** = Customers (apps) making requests UP to the boss
- **EBI** = The boss talking SIDEWAYS to other bosses (other controllers)
- **WBI** = The boss talking to old-school workers who don't speak the new language

#### Key SBI Protocols
- **OpenFlow:** Most popular; defines how controller programs flow tables
- **NETCONF/YANG:** XML-based configuration protocol with data models
- **OVSDB:** Manages Open vSwitch configuration
- **P4Runtime:** Programs P4-programmable switches

#### Key NBI Protocols
- **REST (HTTP):** Most common; CRUD operations on network resources
- **gRPC:** High-performance RPC framework (used by ONOS)

---

### Question 11: OpenFlow, Flow Tables, and the Match-Action Pipeline

#### What is OpenFlow?
OpenFlow is the **most widely used southbound protocol** in SDN. It defines how the SDN controller communicates with switches.

**Analogy:** OpenFlow is the "language" the air traffic controller (SDN controller) uses to talk to planes (switches).

#### How OpenFlow Works
1. Packet arrives at switch → switch checks **flow tables** (pipeline of tables)
2. **Match found** → execute the action (forward, drop, modify, etc.)
3. **No match** → send packet to controller via **Packet-In** message
4. Controller decides → installs new flow rule via **Flow-Mod** message
5. Future matching packets handled by switch **without controller** involvement

#### Flow Table Entry Structure

| Field | Description | Example |
|-------|-------------|---------|
| **Match Fields** | What to match on | Src IP, Dst IP, MAC, Port, VLAN, Protocol |
| **Priority** | Higher priority = checked first | 100 (higher) beats 50 (lower) |
| **Counters** | Statistics | Packet count, byte count |
| **Actions** | What to do with matched packets | Forward to port 3, Drop, Modify header, Send to controller |
| **Timeouts** | When to remove the rule | Idle timeout (no traffic), Hard timeout (absolute) |
| **Cookie** | Controller-assigned label | For tracking/identification |

#### Key OpenFlow Messages

| Message | Direction | Purpose |
|---------|-----------|---------|
| **Packet-In** | Switch → Controller | "I don't know what to do with this packet" |
| **Flow-Mod** | Controller → Switch | "Here's a new rule for handling such packets" |
| **Packet-Out** | Controller → Switch | "Send this specific packet out port X" |
| **Stats-Request/Reply** | Bidirectional | "How many packets matched rule Y?" |
| **Hello** | Bidirectional | Connection setup, version negotiation |
| **Echo** | Bidirectional | "Are you alive?" (keepalive) |

#### Match-Action Pipeline
OpenFlow 1.3+ supports **multiple flow tables** in a pipeline:
```
Packet → [Table 0] → [Table 1] → [Table 2] → ... → [Table n] → Action Set Execution
```
- Each table can match different fields
- A match can send to the next table (`goto-table`) or execute actions
- This enables complex policies (match VLAN in table 0, match IP in table 1, match port in table 2)

#### SDN Controller Platforms

| Controller | Language | Type | SBI Support | NBI | Key Feature |
|-----------|---------|------|-------------|-----|-------------|
| **NOX** | C++ | Centralized | OpenFlow | Custom | First-ever SDN controller |
| **POX** | Python | Centralized | OpenFlow | Python API | Rapid prototyping/education |
| **Ryu** | Python | Centralized | OpenFlow, NETCONF | REST | Lightweight, great for research |
| **Floodlight** | Java | Centralized | OpenFlow | REST | Enterprise-ready, modular |
| **ONOS** | Java | Distributed | OpenFlow, P4 | REST, gRPC | Carrier-grade, high availability (uses Raft consensus) |
| **OpenDaylight** | Java | Distributed | OpenFlow, NETCONF, BGP | RESTCONF | Model-driven (YANG), modular, industry-backed |

---

### Question 12: Controller Placement Problem — Mathematical Formulation

#### What is CPP?
**The problem:** Given a network of switches, decide **how many controllers** to deploy and **where to place** them to optimize performance.

**Analogy:** Where should you place fire stations in a city? Too few = long response times. Too many = expensive. You need the right number in the right locations.

#### Formal Definition
Given a network graph $G = (V, E)$ where $V$ = set of switch nodes, $E$ = set of links:
- Select a subset $P \subseteq V$ of size $k$ as controller locations
- Assign each switch $v \in V$ to its nearest controller $p \in P$

#### Objectives

| Objective | Mathematical Expression | Meaning |
|-----------|----------------------|---------|
| **Minimize Average Latency** | $\min \frac{1}{|V|} \sum_{v \in V} d(v, p(v))$ | Average switch-to-controller delay should be minimized |
| **Minimize Worst-Case Latency** | $\min \max_{v \in V} d(v, p(v))$ | No switch should be too far from its controller |
| **Load Balancing** | $\min \max_{p \in P} |S(p)|$ | Controllers should have roughly equal number of switches |
| **Maximize Reliability** | Ensure each switch can reach ≥2 controllers | Fault tolerance |

Where:
- $d(v, p)$ = shortest path distance (latency) between switch $v$ and controller $p$
- $p(v)$ = the controller assigned to switch $v$
- $S(p)$ = set of switches assigned to controller $p$

#### This is NP-Hard!
CPP is equivalent to the **facility location problem**, which is NP-hard. For large networks, exact solutions are impractical → use heuristics and metaheuristics.

---

### Question 13: Control Plane Performance Metrics for Open-Source SDN Controllers

| Metric | Description | Why It Matters |
|--------|-------------|---------------|
| **Throughput** | Flow setups per second (flows/sec) | Can the controller handle the flow arrival rate? |
| **Latency** | Time from Packet-In to Flow-Mod response | Affects first-packet delay for reactive flows |
| **Scalability** | Max switches/flows managed | Can it handle a large network? |
| **Availability** | Uptime percentage; failover time | Critical for production networks |
| **Consistency** | State sync delay between clustered controllers | Affects correctness of distributed decisions |

#### Controller Comparison

| Metric | Ryu | Floodlight | ONOS | OpenDaylight |
|--------|-----|-----------|------|-------------|
| **Throughput** | ~30K flows/sec | ~100K flows/sec | ~500K flows/sec | ~100K flows/sec |
| **Architecture** | Single-threaded | Multi-threaded | Distributed cluster | Distributed cluster |
| **Failover** | Manual | Manual | Automatic (Raft) | Automatic (Akka) |
| **Use Case** | Research/lab | Medium enterprise | Carrier/ISP/5G | Enterprise/telco |
| **Learning Curve** | Easy (Python) | Moderate (Java) | Steep (Java) | Steep (Java/YANG) |

---

### Question 14: Effective Approaches to Controller Placement

| Approach | How It Works | Pros | Cons |
|----------|-------------|------|------|
| **K-Center** | Minimize the maximum distance from any switch to its controller | Good worst-case guarantees | Ignores average performance |
| **K-Median** | Minimize the total/average distance | Good average performance | May have bad worst-case |
| **Greedy Heuristic** | Iteratively place controllers at the node that most reduces latency | Fast, simple | May not find optimal solution |
| **Genetic Algorithm (GA)** | Evolve a population of placement solutions using crossover + mutation | Good for multi-objective | Slower; needs parameter tuning |
| **PSO** (Particle Swarm) | Particles explore solution space, guided by personal and global best | Good convergence | May get stuck in local optima |
| **ACO** (Ant Colony) | Ants build solutions probabilistically based on pheromone trails | Good for combinatorial problems | Slow for large networks |
| **Simulated Annealing** | Accept worse solutions with decreasing probability to escape local optima | Simple, good exploration | Slow convergence |
| **Pareto Multi-Objective** | Find trade-off front between latency, reliability, cost | Gives multiple choices | Complex to implement |

---

### Question 15: Control Plane Scalability Issues and Approaches

#### Scalability Challenges

| Challenge | Description |
|-----------|-------------|
| **Controller Bottleneck** | Central controller processes ALL Packet-In events; saturates under high flow rates |
| **Flow Table Size** | Switch TCAM (Ternary Content-Addressable Memory) is limited to ~thousands of entries; expensive per entry |
| **Control Channel Latency** | Distant switches have high RTT to controller; delays reactive flow setup |
| **State Consistency** | Distributed controllers must synchronize state; eventual vs strong consistency trade-offs |
| **Topology Discovery** | LLDP overhead grows with network size |

#### Solutions

| Solution | How It Helps |
|----------|-------------|
| **Distributed Controllers** | Deploy ONOS/ODL clusters; partition switches among controllers |
| **Hierarchical Control** | Local controllers handle domains; global controller coordinates across domains |
| **Proactive Flow Rules** | Pre-install rules → fewer Packet-In messages to controller |
| **Flow Aggregation** | Use wildcard rules to match many flows with one entry → reduces TCAM usage |
| **Network Partitioning** | Divide network into smaller controller domains |
| **P4 Programmable Switches** | Handle some decisions locally in the data plane without controller involvement |
| **Caching** | Cache frequent forwarding decisions at switches |

---

### Question 16: Performance Metrics — Latency Minimization and Load Balancing

#### Latency Minimization
**Goal:** Minimize the delay between switches and their assigned controllers.

Two variants:
1. **Average-case:** $\min \frac{1}{|V|} \sum_{v} d(v, c(v))$ — minimize overall average delay
2. **Worst-case:** $\min \max_{v} d(v, c(v))$ — ensure no switch is too far away

**Why it matters:** In reactive mode, every unknown flow must go to the controller. High latency = slow first-packet forwarding = poor user experience.

#### Load Balancing
**Goal:** Distribute switches evenly across controllers so no single controller is overloaded.

**Metric:** $\min \max_{c \in C} \frac{\text{load}(c)}{\text{capacity}(c)}$

**Why it matters:** An overloaded controller becomes a bottleneck, dropping Packet-In messages and causing network failures.

**Trade-off:** Sometimes the nearest controller is already overloaded. You may need to assign a switch to a more distant but less busy controller.

---

### Question 17: Clustering and Metaheuristic Techniques (GA, PSO, ACO) for M-CPP

#### What is M-CPP?
**Multi-Controller Placement Problem (M-CPP):** When you have multiple controllers, deciding where to place each one becomes exponentially complex.

#### Clustering-Based Approach
1. **Step 1:** Cluster switches into groups using K-Means or spectral clustering
2. **Step 2:** Place one controller per cluster (at the cluster center/median)
3. **Advantage:** Naturally balances load and minimizes intra-cluster latency
4. **Disadvantage:** Cluster boundaries may not align with optimal placement

#### Genetic Algorithm (GA)
**Inspired by:** Biological evolution (survival of the fittest)

| Step | What Happens |
|------|-------------|
| **Population** | Generate random placement solutions (chromosomes) |
| **Fitness** | Evaluate each solution (lower latency = higher fitness) |
| **Selection** | Pick the best solutions as parents |
| **Crossover** | Combine two parent solutions to create children |
| **Mutation** | Randomly change a controller location in some children |
| **Repeat** | Until convergence or max generations |

#### Particle Swarm Optimization (PSO)
**Inspired by:** Birds flocking / fish schooling

- Each "particle" is a placement solution
- Particles move through solution space guided by:
  - Their **personal best** position
  - The **global best** position found by any particle
- Particles converge toward the optimal solution

#### Ant Colony Optimization (ACO)
**Inspired by:** Ants finding shortest path to food using pheromones

- "Ants" build solutions step by step
- Good solutions deposit more "pheromone" → attract future ants
- Over iterations, ants converge on the best placement

| Technique | Strength | When to Use |
|-----------|----------|-------------|
| **GA** | Good for multi-objective optimization | When you need to balance latency + reliability + cost |
| **PSO** | Fast convergence | When speed matters; single-objective problems |
| **ACO** | Good for combinatorial problems | When the solution is a discrete set of locations |
| **K-Means + Heuristic** | Simple, fast | Small-to-medium networks; initial placement |

---

### Question 18: Controller Placement in ISP/Telco Networks

#### Data Center vs ISP/Telco Deployment

| Aspect | Data Center | ISP/Telco |
|--------|------------|-----------|
| **Scale** | Hundreds of switches in one location | Thousands of nodes across a country/continent |
| **Latency** | Very low (same building) | High (geographic distances of 100s of km) |
| **Topology** | Regular (leaf-spine, fat-tree) | Irregular (mesh, ring, hierarchical) |
| **Controller Count** | 1–3 (small domain) | Many (10+, placed strategically) |
| **Reliability** | Redundant power/network | Links can fail (fiber cuts, disasters) |
| **Key Concern** | Throughput, microsegmentation | Latency, fault tolerance, regulatory compliance |

#### ISP/Telco Specific Challenges
1. **Geographic spread:** Controllers must be placed to minimize propagation delay across wide areas
2. **Regulatory requirements:** Data may need to stay within country borders
3. **Heterogeneous equipment:** Mix of legacy and SDN devices
4. **High availability:** SLAs require 99.999% uptime → need backup controllers
5. **Traffic patterns:** Diurnal variations; peak hours shift controller load

---

### Question 19: Production Deployments and Emerging Research Directions

#### Notable Production Deployments

| Deployment | Operator | What They Did |
|-----------|---------|--------------|
| **B4** | Google | SDN-managed WAN connecting data centers; 99%+ link utilization via centralized TE |
| **SWAN** | Microsoft | SDN-based WAN for inter-DC traffic engineering |
| **Fabric** | Facebook | Data center SDN fabric with custom switches (Wedge) |
| **CORD** | ONF/AT&T | Central Office Re-architected as Data Center; ONOS-based |
| **SD-WAN** | Various | Enterprise WAN using SDN for branch connectivity |

#### Emerging Research Directions
1. **AI/ML-Driven SDN:** Self-optimizing networks, predictive TE, anomaly detection
2. **Intent-Based Networking:** Express "what" you want, not "how" to configure
3. **P4 Programmable Data Planes:** Custom protocols in hardware
4. **Digital Twin Networks:** Simulate before deploying
5. **Quantum-Safe SDN:** Post-quantum cryptography for control channels
6. **Edge SDN:** SDN at network edge for IoT/MEC

---

### Question 20: P4 — Programming Protocol-independent Packet Processors

#### What is P4?
P4 is a **domain-specific programming language** for defining how packets are processed by network devices (switches, routers, NICs).

**Traditional switches:** Fixed-function ASIC processes only predefined protocols (Ethernet, IP, TCP).  
**P4 switches:** You can **program the switch** to parse and process **any** protocol — including ones you invent!

**Analogy:** 
- Fixed ASIC = A calculator (can only add/subtract/multiply/divide)
- P4 switch = A computer (can be programmed to do anything)

#### SDN + P4 Environment
In traditional SDN (OpenFlow), the controller tells switches WHAT to match and WHAT action to take, but the switch hardware defines WHICH fields can be matched.

With P4, you define:
1. **Which headers** to parse
2. **Which fields** to match
3. **What actions** to perform

```
P4 Program → P4 Compiler → Target-specific binary → Loaded onto switch
```

---

### Question 21: Fixed-Function ASIC vs P4-Programmable Forwarding Device

| Feature | Fixed-Function ASIC | P4-Programmable Device |
|---------|-------------------|----------------------|
| **Protocol Support** | Only pre-defined (Ethernet, IPv4, IPv6, MPLS) | Any protocol — user-defined |
| **Flexibility** | None — must wait for new hardware | Full — reprogram anytime |
| **Header Parsing** | Fixed parser | Programmable parser |
| **Match Fields** | Pre-determined fields | Any field you define |
| **Actions** | Fixed set (forward, drop, modify) | Custom actions |
| **Time to Market** | Years (new ASIC design) | Days (new P4 program) |
| **Performance** | Line rate | Line rate (on P4-capable hardware like Tofino) |
| **Cost** | Lower per unit (mass production) | Higher initially; flexible |
| **Use Cases** | Standard L2/L3 forwarding | In-network computing, INT, custom protocols |

---

### Question 22: Design Goals and the P4_16 Standard

#### P4 Design Goals (the "Three Ps")
1. **Protocol Independence:** Parser and processing are not tied to any specific protocol
2. **Target Independence:** Same P4 program can run on different hardware targets (ASIC, FPGA, software switch)
3. **Reconfigurability:** Switch behavior can be changed at runtime by loading a new P4 program

#### P4_16 Standard
P4_16 is the modern version of P4 (released 2016), replacing P4_14.

**Key features:**
- **Architecture model:** Separates target-dependent and target-independent code
- **Type system:** Strong typing for headers and metadata
- **Extern functions:** Interface to target-specific features (counters, meters, registers)
- **No implicit behaviors:** Everything must be explicitly programmed

---

### Question 23: P4_14 vs P4_16

| Feature | P4_14 | P4_16 |
|---------|-------|-------|
| **Year** | 2014 | 2016 |
| **Architecture** | Monolithic (fixed pipeline model) | Modular (architecture model separates target and program) |
| **Portability** | Target-dependent | **Target-independent** (same program, different targets) |
| **Type System** | Weak | **Strong typing** |
| **Counter/Meter** | Built-in primitives | **Extern objects** (cleaner abstraction) |
| **Control Flow** | Table-centric | **General control blocks** with if/else |
| **Formal Verification** | Limited | Designed for **formal verification** support |
| **Backward Compatible** | — | Can compile P4_14 programs |
| **Code Structure** | Flat | **Hierarchical** (packages, architectures) |

---

### Question 24: Five Core P4_16 Language Abstractions

| Abstraction | Role in Pipeline | Analogy |
|-------------|-----------------|---------|
| **Parser** | Extracts headers from the raw packet bit stream; builds a Parsed Representation | Airport security scanner extracting items from luggage |
| **Control Block** | Applies match-action logic (tables, conditionals) to the parsed packet | The decision-maker: "Based on destination, go to gate 7" |
| **Table** | Defines match fields and associated actions; populated by the control plane | A lookup directory: "If destination = X, action = forward to port 3" |
| **Action** | Defines what to do (forward, drop, modify fields, set metadata) | The instruction: "stamp the passport and proceed" |
| **Extern** | Interface to hardware-specific features (counters, meters, registers, hash functions) | Using special airport equipment (X-ray, passport scanner) |

#### How They Fit Together
```
Packet In → [PARSER] → [INGRESS CONTROL] → [TRAFFIC MANAGER] → [EGRESS CONTROL] → [DEPARSER] → Packet Out
                ↓              ↓                                       ↓
          Extract headers   Tables + Actions                     Reassemble packet
```

---

### Question 25: Four-Stage P4 Development Workflow & Canonical Pipeline

#### Four-Stage Workflow

| Stage | What Happens | Tool |
|-------|-------------|------|
| **1. Write** | Developer writes P4 program defining parser, tables, actions | Text editor / IDE |
| **2. Compile** | P4 compiler translates program to target-specific binary | p4c (reference compiler) |
| **3. Load** | Binary is loaded onto the target device (switch/SmartNIC) | P4Runtime API |
| **4. Populate** | Control plane populates table entries at runtime | P4Runtime / SDN controller |

#### Canonical P4 Packet Processing Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│ Packet → PARSER → INGRESS PIPELINE → TRAFFIC MANAGER →     │
│          EGRESS PIPELINE → DEPARSER → Packet Out            │
└─────────────────────────────────────────────────────────────┘
```

| Stage | Description |
|-------|-------------|
| **Parser** | Reads packet bytes, identifies headers (Ethernet, IP, TCP, custom), extracts fields into metadata |
| **Ingress Pipeline** | Match-action tables applied to incoming packet: routing, ACL, QoS marking |
| **Traffic Manager** | Queuing, scheduling, replication (multicast), buffering — typically NOT programmable (target-specific) |
| **Egress Pipeline** | Post-queuing processing: modify headers, apply egress ACLs, INT stamping |
| **Deparser** | Reassembles the packet from (potentially modified) headers and payload |

---

## Summary Table

| Q# | Topic | Key Takeaway |
|----|-------|-------------|
| 9 | SDN Architecture | 3 layers: App, Control, Infra. Control plane decoupled and centralized |
| 10 | SDN APIs | SBI (down), NBI (up), EBI (sideways), WBI (legacy) |
| 11 | OpenFlow & Flow Tables | Match-action pipeline; Packet-In/Flow-Mod for reactive forwarding |
| 12 | CPP Math Formulation | NP-hard facility location problem; minimize latency + balance load |
| 13 | Controller Metrics | Throughput, latency, scalability, availability, consistency |
| 14 | CPP Approaches | K-center, K-median, GA, PSO, ACO, greedy heuristics |
| 15 | Scalability Issues | Controller bottleneck, TCAM limits, channel latency; solve with distribution/aggregation |
| 16 | Latency & Load Balancing | Minimize avg/max switch-controller latency; balance switch assignments |
| 17 | Metaheuristics for M-CPP | GA (evolution), PSO (swarm), ACO (ants); clustering for initial grouping |
| 18 | ISP/Telco Deployment | Wide-area, heterogeneous, high availability; different from DC deployment |
| 19 | Production & Research | Google B4, Microsoft SWAN, Facebook Fabric; AI-driven SDN, IBN, P4 |
| 20 | P4 Language | Program-the-switch; protocol-independent packet processing |
| 21 | ASIC vs P4 | Fixed protocols vs programmable; P4 enables custom forwarding at line rate |
| 22 | P4_16 Goals | Protocol independence, target independence, reconfigurability |
| 23 | P4_14 vs P4_16 | P4_16: modular architecture, strong typing, better portability |
| 24 | P4_16 Abstractions | Parser, Control Block, Table, Action, Extern |
| 25 | P4 Workflow | Write → Compile → Load → Populate; Parser → Ingress → TM → Egress → Deparser |

---

## 🧠 Memorization Tips

### SDN Layers — "ACI" (top to bottom)
- **A**pplication (apps like firewall, monitor)
- **C**ontrol (controller: ONOS, ODL, Ryu)
- **I**nfrastructure (switches, OpenFlow)

### SDN APIs — "SNEW" (directions)
- **S**outhbound (down to switches)
- **N**orthbound (up to apps)
- **E**ast-West (between controllers)
- **W**estbound (to legacy devices)

### OpenFlow Messages — "PFP" for the Big Three
- **P**acket-In (switch → controller: "Help!")
- **F**low-Mod (controller → switch: "Here's the rule")
- **P**acket-Out (controller → switch: "Send this packet")

### Controller Placement — Remember "LRL"
- **L**atency minimization
- **R**eliability maximization
- **L**oad balancing

### Metaheuristics — "GPS ACE"
- **G**enetic Algorithm (evolution)
- **P**SO (bird flocking)
- **S**imulated Annealing (cooling metal)
- **A**CO (ant pheromones)
- **C**lustering (K-means grouping)
- **E**xact (brute force — only for small networks)

### P4 Pipeline — "PITRED" (pronounce "pit-red")
- **P**arser
- **I**ngress
- **T**raffic Manager
- **R** — (not used, just for the mnemonic)
- **E**gress
- **D**eparser

### P4 Abstractions — "PCTAE"
- **P**arser
- **C**ontrol block
- **T**able
- **A**ction
- **E**xtern

### SDN Controllers by Capability
- **Research:** Ryu (Python, easy), POX (Python, educational)
- **Enterprise:** Floodlight (Java, modular)
- **Carrier-grade:** ONOS (Java, distributed, Raft), OpenDaylight (Java, YANG models)

### Key Production Deployments — "BSF"
- **B**4 (Google WAN)
- **S**WAN (Microsoft WAN)
- **F**abric (Facebook DC)
