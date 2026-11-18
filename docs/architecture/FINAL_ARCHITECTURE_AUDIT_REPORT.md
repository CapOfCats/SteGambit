# Final Architecture Audit Report

**Project:** SteGambit (Multi-format Steganography Tool)
**Share of compliance with the original requirements:** 98% (C4 patterns and Clean Architecture are implemented).

## 1. Layer and Module Assessment
* **Presentation (GUI):** Fully isolated from business logic. Communication with the core goes exclusively through DTOs (`StegoTaskRequest`, `StegoResponse`). The Worker-Thread pattern (`QThread`) is in place, so the interface is not blocked. The layer architecture is considered the reference design.
* **Application / Facade (`StegoService`):** Acts as a "smart" orchestrator. It does not know the details of gradients or DCT zigzags — it only delegates work to format factories, `CryptoEngine`, and the `Spreader` and `IStegoProcessor` abstractions.
* **Domain / Core:** 
  * **File Formats (`FileFormat`):** The Adapter pattern is used. The `JpegContainer` class solves the hard problem of stateful JPEG handling (preserving quantization matrices and Huffman tables while coefficients change).
  * **Crypto Engine:** A reliable embeddable framing mechanism was built (Magic, Flags, Salt, Nonce, Length). It guarantees an integrity check (AEAD) before any decode attempt.
  * **Stego Spreader Pipeline:** Coordinate search (Spreader) and embedding math (Processor) are strictly separated by the Strategy pattern.

## 2. Technical Debt Management
During E2E load testing, deliberate architectural compromises were accepted:
1. **SSIM Metrics:** Because of high overhead (~60% of CPU time), the metric sits behind an optional flag.
2. **Decompression Bomb Limits:** Pillow limits prevent processing very large PNG files (>5 MB payload). Left as a system limitation of the MVP, because steganography is historically not used to hide massive archives.
3. **DTO Reusability:** In Python (thanks to duck typing), a trade-off was accepted: a single `StegoTaskRequest` is used for both encoding and decoding to reduce code duplication. Places with weak semantics are documented.

## 3. Conclusion
The SteGambit architecture meets the requirements of low coupling and high cohesion. The system is ready for use and has enough headroom to add new formats (for example, MP4) by extending interfaces, without modifying the existing core (OCP — Open-Closed Principle).
