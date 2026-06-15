# Section C: Internet of Things (IoT) and Wireless Sensor Networks (WSN) — Questions 26–37

## Overview

The Internet of Things (IoT) is the idea of connecting **everyday physical objects** to the Internet so they can collect data, communicate, and be controlled remotely. Think of your smartwatch sending health data to your phone, a smart thermostat adjusting temperature based on weather, or a factory sensor detecting equipment failure before it happens.

Wireless Sensor Networks (WSN) are a key building block of IoT — networks of tiny, battery-powered sensor nodes that monitor the physical world.

This section covers IoT fundamentals, architectures, WSN, 6LoWPAN, security, and research trends.

---

## Key Concepts

### IoT = Physical World + Internet
- **Sensors** collect data (temperature, motion, pressure)
- **Actuators** take action (open valve, turn on light)
- **Connectivity** sends data to the cloud/edge (Wi-Fi, BLE, LoRa, NB-IoT)
- **Processing** analyzes data (cloud/edge computing, AI/ML)
- **Applications** deliver value (smart home, healthcare, industry)

---

## Questions & Answers

---

### Question 26: What is the IoT? Why IoT?

#### What is IoT?
IoT (Internet of Things) connects **physical objects** ("things") to the Internet, enabling them to sense, communicate, compute, and act.

**Simple definition:** "Making dumb things smart by connecting them to the Internet."

**Examples:**
- Smart refrigerator orders groceries when milk runs low
- Traffic lights adjust timing based on real-time traffic flow
- Farm sensors detect soil moisture and trigger irrigation

#### Why IoT?

| Benefit | Example |
|---------|---------|
| **Automation** | Smart home turns off lights when you leave |
| **Efficiency** | Factory predictive maintenance reduces downtime by 30% |
| **Data-Driven Decisions** | City uses sensor data to optimize bus routes |
| **Cost Reduction** | Remote monitoring eliminates manual inspections |
| **Safety** | Gas leak sensors trigger automatic shutoff |
| **New Services** | Usage-based insurance, connected health |

#### IoT by Numbers
- **Billions of devices** connected (estimated 30+ billion by 2030)
- Every industry is affected: healthcare, agriculture, manufacturing, cities, energy, transport

---

### Question 27: IoT Reference Architecture Models

#### Five-Layer Architecture

```
┌─────────────────────────────────────────────┐
│  BUSINESS LAYER — Business models, profits   │
├─────────────────────────────────────────────┤
│  APPLICATION LAYER — Smart Home, e-Health     │
├─────────────────────────────────────────────┤
│  PROCESSING LAYER — Cloud/Edge, Analytics     │
├─────────────────────────────────────────────┤
│  NETWORK LAYER — IPv6, 6LoWPAN, RPL, MQTT     │
├─────────────────────────────────────────────┤
│  PERCEPTION LAYER — Sensors, Actuators, RFID  │
└─────────────────────────────────────────────┘
```

| Layer | Function | Technologies | Analogy |
|-------|----------|-------------|---------|
| **Perception** | Collects data from the physical world | Sensors, RFID, GPS, cameras | Your eyes and ears |
| **Network** | Transports data from devices to processing | 6LoWPAN, Wi-Fi, LoRa, NB-IoT, RPL | The postal system |
| **Processing** | Stores, processes, analyzes data | Cloud computing, Edge/Fog, Big Data, AI | Your brain |
| **Application** | Delivers services to end users | Smart city, healthcare, agriculture apps | The actions you take |
| **Business** | Business models, monetization, decision-making | Dashboards, ROI analysis | The business plan |

#### Three-Layer Architecture (Simplified)

| Layer | Maps To |
|-------|---------|
| **Perception** | Same as above |
| **Network** | Network + Processing combined |
| **Application** | Application + Business combined |

The five-layer model is more detailed; the three-layer is simpler for basic understanding.

---

### Question 28: WSN Architecture and Topologies

#### What is a WSN?
A Wireless Sensor Network is a collection of **spatially distributed, autonomous sensor nodes** that cooperatively monitor physical conditions and pass data to a central sink.

**Analogy:** A network of weather stations scattered across a country, each reporting to a central meteorological center.

#### WSN Node Hardware Architecture

Every sensor node has four components:

| Component | Function | Constraint |
|-----------|----------|-----------|
| **Sensing Unit** | Measures physical phenomenon (temperature, humidity, vibration) | Limited accuracy |
| **Processing Unit** | Microcontroller (e.g., MSP430, ARM Cortex-M) processes data locally | Limited CPU, memory |
| **Transceiver** | Sends/receives wireless data (IEEE 802.15.4, BLE) | Limited range (10–100m) |
| **Power Unit** | Battery (AA, coin cell) or energy harvesting | Most critical constraint |

#### Deployment Topologies

| Topology | Description | Use Case |
|----------|------------|----------|
| **Star** | All nodes communicate directly with the sink | Small area, low hop count |
| **Mesh** | Nodes relay data through multiple hops; redundant paths | Large area, robust networks |
| **Tree/Cluster** | Nodes organized in clusters; cluster heads aggregate and forward | Energy-efficient, scalable |
| **Hybrid** | Combination of star + mesh | Flexible deployment |

---

### Question 29: Software-Defined IoT and WSN

#### What is SD-IoT?
Applying SDN principles to IoT networks: **separate control from data plane** in IoT devices, centralize management in an SDN controller.

#### Why SD-IoT?

| Challenge Without SDN | How SDN Solves It |
|----------------------|------------------|
| Heterogeneous devices (Zigbee, BLE, Wi-Fi) | Centralized controller manages all protocols |
| Manual configuration doesn't scale to millions of devices | Automated, programmable configuration |
| No global network view | Controller has complete topology view |
| Static routing wastes energy | Dynamic routing adapts to link quality and energy |
| Hard to enforce security policies | Centralized policy enforcement; isolate compromised devices |

#### SD-WSN Architecture
```
┌─────────────────────────────────┐
│     SDN Controller               │
│  (Routing, QoS, Security)       │
├────────── SBI ──────────────────┤
│     IoT Gateway / Border Router  │
├─────────────────────────────────┤
│  Sensor Nodes (data plane only) │
└─────────────────────────────────┘
```

**Challenges:**
- Resource-constrained devices may not support OpenFlow
- Energy overhead of SDN control messages
- Controller scalability with millions of devices

---

### Question 30: Application Domains and Key Challenges of IoT

#### Application Domains

| Domain | Applications | Key Technologies |
|--------|-------------|-----------------|
| **Smart Home** | Lighting, HVAC, security cameras, voice assistants | Wi-Fi, Zigbee, BLE, Z-Wave |
| **Smart City** | Traffic management, parking, waste management, air quality | LoRaWAN, NB-IoT, 5G |
| **Healthcare** | Wearable monitors, remote patient monitoring, drug tracking | BLE, Wi-Fi, 6LoWPAN |
| **Agriculture** | Soil moisture, precision irrigation, drone surveillance | LoRa, satellite IoT |
| **Industrial IoT (IIoT)** | Predictive maintenance, supply chain, robotics | 5G URLLC, TSN, Wi-Fi 6 |
| **Energy** | Smart grid, smart metering, renewable monitoring | PLC, NB-IoT, LoRa |
| **Transportation** | Connected vehicles, fleet tracking, autonomous driving | 5G V2X, DSRC |

#### Key Challenges

| Challenge | Description |
|-----------|-------------|
| **Security & Privacy** | Billions of devices = massive attack surface; weak default passwords; Mirai botnet |
| **Interoperability** | Different vendors, protocols, standards don't work together |
| **Scalability** | Managing billions of devices, petabytes of data |
| **Energy** | Battery-powered devices must last years |
| **Standardization** | Too many competing standards (Zigbee, Z-Wave, Thread, Matter) |
| **Data Management** | Volume, velocity, variety of data; storage and processing |
| **Connectivity** | Coverage in remote areas; indoor penetration |
| **Cost** | Device, connectivity, and cloud costs at scale |

---

### Question 31: Interoperability for IPv6 and IoT

#### The Problem
IoT devices use constrained protocols (IEEE 802.15.4, BLE) with small frame sizes and limited resources. IPv6 requires minimum 1280-byte MTU. These don't naturally work together.

#### The Solution: 6LoWPAN and Protocol Translation

| Layer | Standard IP | IoT Adaptation |
|-------|-----------|---------------|
| **Application** | HTTP | CoAP (lightweight RESTful) |
| **Transport** | TCP | UDP (less overhead) |
| **Network** | IPv6 | 6LoWPAN (header compression) |
| **Link** | Ethernet/Wi-Fi | IEEE 802.15.4, BLE |

#### How IPv6 Enables IoT Interoperability
1. **End-to-end addressing:** Every IoT device gets a globally unique IPv6 address
2. **No NAT needed:** 128-bit address space is large enough
3. **Standard protocols:** CoAP over UDP over IPv6 works end-to-end
4. **6LoWPAN compression:** Makes IPv6 feasible on constrained networks
5. **Border router:** Translates between 6LoWPAN and standard IPv6

---

### Question 32: Global Distribution of IoT Projects

| Region | Share | Key Focus Areas |
|--------|-------|----------------|
| **Americas** (USA, Canada, South America) | ~45–50% | Smart cities, industrial IoT, connected health, agriculture |
| **Europe** | ~30–35% | Smart cities (Barcelona, Amsterdam), Industry 4.0, energy, GDPR-compliant solutions |
| **APAC** (Asia-Pacific) | ~20–25% | Smart manufacturing (China, Japan, Korea), smart cities (Singapore, India), agriculture |

**Key observations:**
- USA leads in IoT investment and innovation
- Europe focuses on regulation and privacy (GDPR)
- China is the largest IoT device manufacturer
- India is rapidly growing in smart city deployments
- Cross-regional interoperability is a challenge

---

### Question 33: 6LoWPAN Network Architecture

#### What is 6LoWPAN?
**6LoWPAN** = IPv6 over Low-Power Wireless Personal Area Networks.

It's an **adaptation layer** that enables IPv6 to work over IEEE 802.15.4 networks (which have tiny 127-byte frames).

**Analogy:** 6LoWPAN is like a translator who takes a long English speech and compresses it into short tweets that fit the character limit, then reconstructs the full speech at the other end.

#### Architecture
```
┌──────────────────┐          ┌──────────────────┐
│   IPv6 Internet   │          │  6LoWPAN Network  │
│                   │◄────────►│  (802.15.4)       │
│  Standard IPv6    │  Border  │  Sensor nodes     │
│  hosts/servers    │  Router  │  with compressed  │
│                   │          │  IPv6              │
└──────────────────┘          └──────────────────┘
```

#### Protocol Stack
```
┌────────────────────┐
│ Application (CoAP) │
├────────────────────┤
│ UDP                │
├────────────────────┤
│ IPv6               │
├────────────────────┤
│ 6LoWPAN Adaptation │  ← This is the magic layer
├────────────────────┤
│ IEEE 802.15.4 MAC  │
├────────────────────┤
│ IEEE 802.15.4 PHY  │
└────────────────────┘
```

#### Key 6LoWPAN Mechanisms

| Mechanism | What It Does |
|-----------|-------------|
| **Header Compression (IPHC)** | Compresses 40-byte IPv6 header to as few as 2 bytes using context-based compression |
| **Fragmentation** | Splits large IPv6 packets into multiple 802.15.4 frames (127 bytes max) |
| **Mesh Addressing** | Enables multi-hop forwarding at the link layer using mesh headers |
| **Optimized NDP** | Reduces multicast overhead of Neighbor Discovery for lossy networks (RFC 6775) |

---

### Question 34: OSI Model, Wi-Fi Stack, and 6LoWPAN Stack

| OSI Layer | Wi-Fi Stack | 6LoWPAN Stack |
|-----------|-----------|--------------|
| **Application** | HTTP, FTP, SMTP | CoAP, MQTT |
| **Transport** | TCP, UDP | UDP (TCP too heavy) |
| **Network** | IPv4/IPv6 | IPv6 (with 6LoWPAN compression) |
| **Adaptation** | — | **6LoWPAN** (header compression + fragmentation) |
| **Data Link** | IEEE 802.11 (Wi-Fi) | IEEE 802.15.4 MAC |
| **Physical** | IEEE 802.11 PHY (2.4/5 GHz) | IEEE 802.15.4 PHY (2.4 GHz, 868/915 MHz) |

#### Key Differences
- Wi-Fi: High bandwidth (Mbps–Gbps), high power, no adaptation needed for IPv6
- 6LoWPAN: Low bandwidth (250 kbps), low power, **needs adaptation layer** to fit IPv6 into tiny frames

---

### Question 35: Why 6LoWPAN is Required for IPv6 over IEEE 802.15.4

#### The Mismatch Problem

| Parameter | IPv6 Requirement | IEEE 802.15.4 Capability |
|-----------|-----------------|------------------------|
| **Minimum MTU** | 1280 bytes | **127 bytes** (max frame) |
| **Header size** | 40 bytes (IPv6) + 8 bytes (UDP) = 48 bytes minimum | Only 81 bytes available for payload after MAC header |
| **Address size** | 128-bit (16 bytes) per address | — |

Without 6LoWPAN, a single IPv6 header (40 bytes) + UDP header (8 bytes) = 48 bytes would consume most of the 802.15.4 frame, leaving almost no room for actual data!

#### How 6LoWPAN Solves This

| Solution | How |
|----------|-----|
| **Header Compression** | Compresses 40-byte IPv6 header to 2–7 bytes by eliding link-local prefixes, inferring fields from link layer |
| **Fragmentation/Reassembly** | Breaks large IPv6 packets into multiple small 802.15.4 frames |
| **Mesh Routing** | Enables multi-hop at link layer (not every node needs full IP routing) |

**Result:** Sensor nodes become **first-class IPv6 citizens** with end-to-end IP connectivity, without needing application-layer gateways.

---

### Question 36: IoT Security Threat Landscape — Root Causes of IoT Vulnerability

#### Why IoT is Uniquely Vulnerable

| Root Cause | Explanation |
|-----------|-------------|
| **Resource Constraints** | Limited CPU/memory → can't run complex encryption/authentication |
| **Scale** | Billions of devices → massive attack surface |
| **Default Credentials** | Many devices ship with admin/admin or no password |
| **No Update Mechanism** | Devices deployed for years with no firmware update capability |
| **Physical Accessibility** | Devices deployed in public places → physical tampering |
| **Heterogeneity** | Many vendors, protocols, OS → inconsistent security |
| **Long Lifecycle** | IoT devices may be deployed for 10+ years → outlive security support |

#### Threat Landscape

| Threat | Description | Example |
|--------|-------------|---------|
| **Botnets/DDoS** | Compromised IoT devices form botnets | Mirai botnet (2016): 600K devices, 1.2 Tbps DDoS |
| **Eavesdropping** | Intercepting unencrypted sensor data | Reading smart meter data to determine when house is empty |
| **Man-in-the-Middle** | Intercepting and altering communication | Modifying insulin pump commands |
| **Replay Attack** | Retransmitting captured legitimate packets | Replaying door unlock command |
| **Node Capture** | Physical access to extract cryptographic keys | Extracting keys from a sensor left in a field |
| **Sybil Attack** | One malicious node fakes multiple identities | Faking multiple sensor readings to manipulate data |
| **Firmware Tampering** | Installing malicious firmware via insecure OTA updates | Bricking devices or installing backdoors |
| **Side-Channel** | Power/timing analysis to extract secrets | Extracting AES key from power consumption patterns |

#### Mitigation by Layer

| Layer | Mitigations |
|-------|-------------|
| **Device** | Secure boot, hardware root of trust (TPM), tamper-resistant enclosures |
| **Communication** | DTLS/TLS encryption, AES link-layer encryption |
| **Network** | Firewall rules, IDS, SDN-based anomaly detection |
| **Application** | OAuth 2.0, input validation, secure APIs |
| **Data** | Encryption at rest, anonymization, integrity checks |

---

### Question 37: Research Trends in IoT and WSN

| Research Area | Description |
|--------------|-------------|
| **AI/ML at the Edge** | Running ML models on IoT devices for real-time inference (TinyML) |
| **Digital Twins** | Virtual replicas of physical IoT systems for simulation and optimization |
| **Blockchain for IoT** | Decentralized trust, secure data sharing, device identity management |
| **Energy Harvesting** | Solar, vibration, thermal, RF energy to extend device lifetime |
| **6G and IoT** | THz communication, holographic communication, ultra-massive MIMO |
| **Semantic IoT** | Devices understand and reason about data (ontologies, knowledge graphs) |
| **Federated Learning** | Train ML models across IoT devices without sharing raw data (privacy) |
| **Zero Trust IoT** | Never trust any device; continuous authentication and verification |
| **Software-Defined IoT** | SDN/NFV for programmable, flexible IoT networks |
| **LPWAN Evolution** | LoRaWAN, NB-IoT, LTE-M advancements for wider coverage and lower power |

---

## Summary Table

| Q# | Topic | Key Takeaway |
|----|-------|-------------|
| 26 | What/Why IoT | Connecting physical objects to Internet; automation, efficiency, data-driven decisions |
| 27 | IoT Architecture | 5-layer (Perception→Network→Processing→Application→Business) or 3-layer simplified |
| 28 | WSN Architecture | Sensor nodes (sense+process+transmit+power); topologies: star, mesh, tree |
| 29 | SD-IoT/WSN | Apply SDN to IoT: centralized control, programmable, dynamic routing |
| 30 | Applications & Challenges | Smart home/city/health/agriculture/industry; security, scalability, energy, interop |
| 31 | IPv6 IoT Interoperability | 6LoWPAN + CoAP enable end-to-end IPv6 connectivity for constrained devices |
| 32 | Global IoT Distribution | Americas ~50%, Europe ~30%, APAC ~20%; USA leads, China manufactures |
| 33 | 6LoWPAN Architecture | Adaptation layer: header compression (40B→2B), fragmentation, mesh addressing |
| 34 | OSI/Wi-Fi/6LoWPAN Stacks | 6LoWPAN adds adaptation layer between IPv6 and 802.15.4 |
| 35 | Why 6LoWPAN Needed | IPv6 needs 1280B MTU; 802.15.4 has 127B frames; 6LoWPAN bridges the gap |
| 36 | IoT Security | Resource constraints, scale, default creds → botnets, MitM, node capture |
| 37 | Research Trends | TinyML, digital twins, blockchain, energy harvesting, federated learning, zero trust |

---

## 🧠 Memorization Tips

### IoT 5-Layer Architecture — "PNPAB" = "**P**lease **N**ever **P**unch **A** **B**ear"
- **P**erception (sensors)
- **N**etwork (connectivity)
- **P**rocessing (cloud/edge analytics)
- **A**pplication (smart services)
- **B**usiness (money/decisions)

### WSN Node Components — "SPTP" = "**S**ense **P**rocess **T**ransmit **P**ower"
- Sensing unit
- Processing unit
- Transceiver
- Power unit

### 6LoWPAN Key Mechanisms — "HFMN"
- **H**eader compression (40B → 2B)
- **F**ragmentation (split big packets)
- **M**esh addressing (multi-hop)
- **N**DP optimization (reduce overhead)

### IoT Security Threats — "BERMNS" (think "BURNS")
- **B**otnets/DDoS
- **E**avesdropping
- **R**eplay attacks
- **M**an-in-the-Middle
- **N**ode capture
- **S**ybil attack

### Why IoT is Vulnerable — "RSDNPH" = "**R**esource constraints, **S**cale, **D**efault creds, **N**o updates, **P**hysical access, **H**eterogeneity"

### Key Numbers
- 802.15.4 max frame: **127 bytes**
- IPv6 min MTU: **1280 bytes**
- IPv6 header: **40 bytes** → compressed to **2 bytes** by 6LoWPAN
- IoT devices projected: **30+ billion by 2030**
