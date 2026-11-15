# SDN Performance Evaluation: Baseline vs Dynamic QoS

## 1. Executive Summary

The experiment records compare the baseline SDN configuration with Dynamic SDN under normal and congested background-traffic conditions, using 5, 10, and 20 concurrent students.

For the congested scenarios, the recorded results show:

- Average latency reduction: **34.4%–64.7%**.
- P95 latency reduction: **35.2%–47.9%**.
- Throughput increase: **52.6%–174.3%**.
- Packet loss: **0% in both architectures** in every recorded scenario.
- Exam completion: **100% in all recorded scenarios**.

The Dynamic SDN result records mark `sdn_policy_active` as true in all congested scenarios and false in all normal scenarios. These flags should be cross-checked against controller logs and switch flow/queue state before claiming independently verified live policy enforcement.

## 2. Detailed Results

The following table compares the recorded measurements. Latency change is expressed as reduction (positive is better); throughput change is expressed as increase (positive is better).

| Students | Condition | Avg latency B → D (ms) | Reduction | P95 B → D (ms) | Reduction | Throughput B → D (req/s) | Increase | Jain B → D | Delta | Packet loss B → D |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | Normal Traffic | 6.00 → 5.46 | +9.0% | 25.832 → 20.770 | +19.6% | 199.63 → 196.21 | -1.7% | 0.9336 → 0.9457 | +0.0121 | 0.0% → 0.0% |
| 5 | Congested (Background Traffic) | 6.81 → 4.47 | +34.4% | 23.265 → 12.121 | +47.9% | 93.49 → 256.48 | +174.3% | 0.9243 → 0.9938 | +0.0695 | 0.0% → 0.0% |
| 10 | Normal Traffic | 6.39 → 10.38 | -62.4% | 20.605 → 58.800 | -185.4% | 335.42 → 313.37 | -6.6% | 0.9697 → 0.9728 | +0.0031 | 0.0% → 0.0% |
| 10 | Congested (Background Traffic) | 23.75 → 10.30 | +56.6% | 66.793 → 38.844 | +41.8% | 205.45 → 313.52 | +52.6% | 0.9925 → 0.9909 | -0.0016 | 0.0% → 0.0% |
| 20 | Normal Traffic | 25.36 → 28.16 | -11.0% | 108.197 → 123.663 | -14.3% | 336.64 → 312.57 | -7.2% | 0.9990 → 0.9918 | -0.0072 | 0.0% → 0.0% |
| 20 | Congested (Background Traffic) | 53.81 → 19.00 | +64.7% | 139.411 → 90.388 | +35.2% | 194.74 → 474.94 | +143.9% | 0.9953 → 0.9860 | -0.0093 | 0.0% → 0.0% |

## 3. Interpretation

- The congested runs show lower recorded average and P95 response latency and higher throughput with Dynamic SDN.
- Jain's fairness index improves in the five-student congested run, but is slightly lower in the 10- and 20-student congested runs. Therefore, a universal fairness improvement should not be claimed.
- No packet loss was recorded in either architecture, so these results do not demonstrate packet-loss elimination.
- Normal-traffic results are included as a control condition. They do not show a consistent performance advantage for Dynamic SDN.

## 4. Charts

- [Latency Comparison](latency_comparison.png)
- [Throughput and Fairness Comparison](throughput_fairness_comparison.png)

## 5. Measurement Limitations

The supplied result files contain one aggregate record for each student-count and traffic-condition combination. They do not provide repeat-run statistics, standard deviations, or confidence intervals. The results should therefore be presented as measurements from these runs, not as statistically established guarantees.

Before the final demonstration, independently verify congestion detection, QoS queue installation, and recovery using live controller logs and Open vSwitch flow/queue inspection.
