# Manual acceptance scenarios (Smoke Test Cases)

This document contains atomic user scenarios for checking the stability of critical functionality (black-box testing) before release.

---

### Scenario 1: Spatial steganography (embedding in PNG)
**Goal:** Verify the end-to-end LSB pipeline for lossless images.
**Inputs:**
* Cover (carrier): `image.png` (for example, 1920x1080)
* Payload (secret): `secret_doc.pdf`
* Password: `TestPass123`

| Step | User action | Expected result (system response) |
| :--- | :--- | :--- |
| **1** | Launch the application and open the **[ ENCODE ]** tab. | The data-hiding interface is displayed. |
| **2** | Select `image.png` in the Cover File field. | The controller recognizes the Magic Bytes and displays the algorithm: `LSB`. |
| **3** | Select `secret_doc.pdf` in the Payload File field and click "Check Compatibility". | A capacity report is calculated. The "HIDE DATA" button is enabled. |
| **4** | Click "HIDE DATA", enter the password, choose the path `stego_result.png`, and start the process. | The file `stego_result.png` is generated. Analytics show PSNR > 40 dB and process status "OK" (green). |
| **5** | Open the **[ DECODE ]** tab, select `stego_result.png`, enter the password `TestPass123`, and click "EXTRACT". | The file is extracted successfully (the `.pdf` extension is restored automatically). The operating system opens the document without errors. |

---

### Scenario 2: Frequency-domain steganography (JSteg embedding in JPEG)
**Goal:** Verify that the DCT-coefficient algorithms work.
**Inputs:**
* Cover: `photo.jpg`
* Payload: `archive.zip`
* Password: `JpegStego`

| Step | User action | Expected result (system response) |
| :--- | :--- | :--- |
| **1** | Select the cover file `photo.jpg`. | The controller displays the algorithm: `DCT (frequency domain)`. |
| **2** | Select the payload file `archive.zip` and click "Check Compatibility". | The system dynamically evaluates the AC-coefficient pools and approves the capacity. |
| **3** | Hide the data and save it as `stego_photo.jpg`. | The size of the resulting `.jpg` file changes only slightly. No visual artifacts are present. |
| **4** | Run DECODE on `stego_photo.jpg`. | The system recognizes the extracted blob and saves it as `.zip`. The archive unpacks with no integrity errors. |

---

### Scenario 3: Audio steganography (embedding in WAV)
**Goal:** Verify handling of 1D arrays of audio samples.
**Inputs:**
* Cover: `music.wav`
* Payload: `image.jpg`
* Password: `WavePass`

| Step | User action | Expected result (system response) |
| :--- | :--- | :--- |
| **1** | Load `music.wav` as the cover and `image.jpg` as the payload. | The format is identified as WAV and the algorithm as `LSB`. |
| **2** | Embed the data and review the metrics. | The Deviation metric (size change) is strictly 0% (because WAV is lossless). |
| **3** | Play the generated WAV file in any media player. | The file plays correctly. Audible artifacts (crackling or noise) are absent. |

---

### Scenario 4: Capacity overflow protection (Capacity Overflow)
**Goal:** Verify that `CapacityReport` prevents the file from being damaged.
**Inputs:**
* Cover: `small_icon.png` (64x64 resolution)
* Payload: `large_video.mp4` (a file larger than 10 MB)

| Step | User action | Expected result (system response) |
| :--- | :--- | :--- |
| **1** | Load the mismatched files into `Cover` and `Payload`. | The fields are filled successfully. |
| **2** | Click "Check Compatibility". | The report shows insufficient capacity (Utilization > 100%). The text is colored red (`TOO LARGE`). |
| **3** | Try to start the hiding process. | The "HIDE DATA" button is disabled (it cannot be clicked). A degraded file is not created. |

---

### Scenario 5: Anti-conversion controller
**Goal:** Confirm that the system blocks an invalid extension change.
**Inputs:**
* Cover: `photo.jpg`
* Output path: `C:/Output/stego.png` (user error)

| Step | User action | Expected result (system response) |
| :--- | :--- | :--- |
| **1** | Select a cover in a valid format (`.jpg`) and pass the capacity check. | The "HIDE" button becomes active. |
| **2** | In the save dialog for the resulting stego file, manually set the extension to `.png`. | The interface accepts the path. |
| **3** | Click "Start Spreading Bits" in the dialog. | The operation is aborted. The logs show the exception: `Нарушение анти-конверсии: носитель JPEG, но выходящий формат .png`. No file is generated. |

---

### Scenario 6: Authentication failure (Wrong Password)
**Goal:** Verify cryptographic protection (the key-derivation mechanism).
**Inputs:**
* A valid stego carrier `stego.png` (encoded with the password `MySecret123`).
* Password under test: `mysecret123` (wrong case) or `Wrong`.

| Step | User action | Expected result (system response) |
| :--- | :--- | :--- |
| **1** | Open the **[ DECODE ]** tab and select `stego.png`. | The file is accepted. |
| **2** | Enter the wrong password `mysecret123` and click "EXTRACT". | The log panel shows an error from `CryptoEngine` (missing `MAGIC bytes`, or a decryption error). |
| **3** | Check the output directory. | The secret file is NOT generated (corrupt or garbage files are not saved). |

---

### Scenario 7: Data-integrity protection (GCM MAC-tag mismatch)
**Goal:** Evaluate the AEAD subsystem (authenticated encryption).
**Inputs:**
* A valid stego carrier `stego_image.png`.

| Step | User action | Expected result (system response) |
| :--- | :--- | :--- |
| **1** | Open `stego_image.png` in an editor (for example, MS Paint), change the color of one pixel with the brush, and save the file. | The file is saved with the hidden payload corrupted. |
| **2** | Load this image on the **[ DECODE ]** tab and enter the *correct* password. | Extraction starts. |
| **3** | Watch the process. | `CryptoEngine.decrypt` raises an exception: the authentication tag was modified (`InvalidFrame`). The operation is rejected. |

---

### Scenario 8: Handling clean files (Zero-Trust)
**Goal:** Check system behavior when extraction is attempted on an ordinary media file.
**Inputs:**
* Any random media file `regular_pic.jpg` downloaded from the internet.

| Step | User action | Expected result (system response) |
| :--- | :--- | :--- |
| **1** | On the **[ DECODE ]** tab, select the downloaded `regular_pic.jpg`. | The file is accepted for processing. |
| **2** | Enter any password and click "EXTRACT". | Reading the pseudorandom bits returns entropy noise. |
| **3** | Finish the check. | The system does not find the `SGB1` security signature in the noise. A readable error is shown: `MAGIC bytes не найдены. Возможно, файл не содержит данных`. The UI does not crash. |
