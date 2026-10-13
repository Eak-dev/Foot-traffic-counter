# Third-party notices

Cloud probe protocol/signing implementation is adapted from OnTapo at commit a387f6abddb72f7e6eea72b374df5ad189da1f5f: https://github.com/noriellecruz/ontapo . This is an unofficial interoperability experiment, not vendor endorsement or a tested C545D downloader. Public app-signing constants are from that source, not Owner account secrets.

The public TP-Link Cloud Root CA is extracted from that commit's mergedCA.pem (certificate DER SHA256 8d27224dac20c2db8a380e3103b4e383c481ee41b681908579aee416761da289), corroborated byte-for-byte in piekstra/tplink-cloud-api v5.2.0 commit 7b8773eb784e6eba3dd5cdf93fa99b610921ab9d, tplinkcloud/certs/tplink-ca-chain.pem. This is community-source corroboration, not direct verification from a vendor-distributed APK. Only the one needed root is bundled; it is loaded per process and never into the OS store.

MIT License

Copyright (c) 2026 Norielle Cruz

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


## Native download packet reference

The experimental download packet contract was independently constructed after static review of pytapo3.4.26 media_stream/downloader.py (MIT, Copyright (c)2020 Juraj Nyíri). No SDK constructor, recovery or integration tests are executed. Pytapo license follows for attribution.

MIT License

Copyright (c) 2020 Juraj Nyíri

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## OD49 local people counting dependencies

OpenCV DNN / YOLOX_s ONNX from [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/object_detection_yolox), Apache-2.0. Model SHA256 `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063`,35,858,002bytes. Local inference only; model is ONNX, no pickle/executable checkpoint. Source contributor Sri Siddarth Chakaravarthy/OpenCV; related upstream Megvii YOLOX. Decoding/preprocessing follows the public format, our integration is modified/independently implemented. Full license: [Apache-2.0](licenses/YOLOX-APACHE-2.0.txt).

Tracking uses supervision0.26.1 ByteTrack, MIT Copyright(c)2022Roboflow, full [license](licenses/SUPERVISION-MIT.txt). No hosted inference, cloud client calls, face recognition or appearance embeddings. The dependency includes unrelated cloud helper APIs; this application does not call them. Process-level macOS network denial is verified before library imports.

Pinned runtime: opencv-python4.11.0.86, numpy2.2.6, scipy1.15.3, supervision0.26.1 onnxruntime1.23.2(MIT) plus29total packages in requirements-counting.lock with distribution hashes. NumPy/SciPy BSD licenses and bundled runtime notices remain in installed distributions, OpenCV Apache-2.0. Do not redistribute wheels without their included notices. OSV version query2026-10-13 returned no known advisories for these29installed versions; this is a point-in-time check, not a security guarantee. No package build from source, paid subscription or system Python modification.

ONNX Runtime is used as CPU inference backend after a synthetic640x640 benchmark (0.363–0.513s/forward) and real local pilot. [Official release](https://github.com/microsoft/onnxruntime/releases/tag/v1.23.2); installed distribution retains its MIT license and third-party notices. OpenCV remains the frame/annotation/preprocessing library.
