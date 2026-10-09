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
