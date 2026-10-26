# Repo và workflow cho 1× Tesla P100 16 GB

Tài nguyên phát triển đã chốt bởi người dùng: **một P100 16 GB trên server hiện có**. Không thuê GPU khác. Chưa xác định SSH host/thư mục server hoặc thời lượng chạy dài; chưa kết nối hoặc cài gì lên server trong lượt chuẩn bị này.

## Cách tổ chức

```text
datamate/                  # Git repo: source, configs, docs, tests, split manifests
  train/                   # unpack riêng, không track raw data trong Git
  public_test/rulebook.md   # documentary source cho register, chưa chạy public
  models/                  # local weights, không Git
  .venv-p100/              # môi trường riêng server, không Git
  runs/<run_id>/           # logs, output, config/model/data hashes, không Git
```

Root `.git` của workspace local đang được môi trường quản lý read-only và chưa là repo hợp lệ. `scripts/package_repo.py` tạo **repo Git độc lập** trong `artifacts/<package>/repo`, Git bundle để clone và source archive. Không sửa `.git` được quản lý, không tạo remote hoặc publish.

Gói mặc định được chuẩn bị cho server gồm `datamate.bundle`, `source.tar.gz`, `train.tar.gz`, `evidence.tar.gz`, `PACKAGE_MANIFEST.json` và `SHA256SUMS`. Data/weights/runs/credentials tách khỏi code Git. Repo có tài liệu cuộc thi do người dùng cung cấp, nên giữ riêng tư khi chọn hosting.

## Đưa lên server

Sau khi có host/path, chuyển các file gói sang server bằng scp/rsync theo kết nối của bạn. Chạy tại thư mục chứa gói:

```bash
sha256sum -c SHA256SUMS
git clone datamate.bundle datamate
tar -xzf train.tar.gz -C datamate
tar -xzf evidence.tar.gz -C datamate
cd datamate
bash scripts/server/test_cpu.sh
```

Không dùng `git init` trên root workspace local. Nếu server không có Git, có thể giải nén `source.tar.gz` vào thư mục mới thay bước clone; các bước còn lại giống nhau. Bundle là snapshot ban đầu, cập nhật lâu dài qua một remote private do người dùng chỉ định hoặc bundle mới; không rsync đè một Git checkout đang có thay đổi.

## Môi trường P100

Đề xuất khởi điểm: Linux x86_64, **Python 3.11**, PyTorch **2.6.0 cu118**, Transformers **4.51.3**, FP16 và eager attention. P100 là compute capability 6.0 theo [NVIDIA](https://developer.nvidia.com/cuda/gpus/legacy). [Mã build PyTorch v2.6.0](https://github.com/pytorch/pytorch/blob/v2.6.0/.ci/manywheel/build_cuda.sh) bao gồm 6.0 cho CUDA 11.8/12.4; [hướng dẫn wheel chính thức](https://pytorch.org/get-started/previous-versions/) có các lựa chọn tương ứng.

Đây là environment candidate đã đối chiếu nguồn, **chưa được chạy trên P100 của người dùng**. Phải kiểm tra driver, wheel architecture và phép tính thật; không coi chữ CUDA trong nvidia-smi là bằng chứng wheel hỗ trợ sm_60. Không nâng torch/CUDA tùy ý theo phiên bản mới nhất.

```bash
PYTHON_BIN=python3.11 bash scripts/server/setup_p100.sh
CUDA_VISIBLE_DEVICES=0 .venv-p100/bin/python scripts/gpu_preflight.py --output runs/p100_preflight_001.json
```

Setup tạo venv riêng, cài pinned direct dependencies và package editable; cần network ở **bước chuẩn bị môi trường**. Không thay system Python, driver hoặc cài CUDA system. Nếu driver phù hợp và muốn thử cu124, chọn `TORCH_FLAVOR=cu124` với venv khác, rồi chạy lại preflight. Chưa cài thành công thì chưa có dependency lock transitive đã kiểm chứng. Sau setup thành công, lưu `pip freeze` và report driver/wheel cùng run.

## Giới hạn vận hành ban đầu

Profile: `configs/hardware/p100_16gb.json`.

| Mục | Giới hạn khởi điểm |
|---|---|
| GPU/process | 1, chọn bằng CUDA_VISIBLE_DEVICES |
| Dtype / attention | float16 / eager |
| Batch | 1 |
| Input / generated tokens | 2.048 / 256 |
| Model budget lúc đầu | ≤4B parameters, tối đa 13 GiB PyTorch allocator budget |
| Model format | Local safetensors, built-in architecture, không remote code |
| Training / dài giờ | Chưa bật; cần chốt wall-time trước |

VRAM budget không bảo đảm context này vừa cho mọi kiến trúc, không kiểm soát các process GPU khác và không phải giới hạn tổng RAM/VRAM tuyệt đối. Bắt đầu model nhỏ, đo peak memory và throughput rồi mới tăng context/model. Không load toàn bộ raw tables vào prompt; giữ ingestion/tính toán trên CPU, chỉ gửi schema/rules/evidence cần thiết cho planner.

Một model nhỏ được benchmark trước; không chọn model cuối chỉ theo kích thước. Mọi model inference cuối cùng vẫn cần license, ngày weights public trước 01/10/2026, inventory tổng parameters ≤15B và validation phù hợp. Chưa chọn hoặc tải model trong lượt này.

## Smoke test với weights đã có

```bash
CUDA_VISIBLE_DEVICES=0 .venv-p100/bin/python scripts/smoke_local_model.py --model models/YOUR_LOCAL_MODEL --output runs/p100_model_smoke_001
```

Đường dẫn là placeholder cho thư mục model có thật. Script offline/local-only, đếm parameters trước load, áp profile, sinh tối đa 32 tokens bằng prompt kiểm tra nhỏ và ghi memory/runtime/errors. **Đây là kiểm tra môi trường, không phải DataMate predictor hoặc benchmark PA.** Không training, không đọc test data, không download weights. Nếu OOM hoặc kernel lỗi, giữ report và giảm model/context sau khi xác định nguyên nhân; không tự chuyển sang BF16/FlashAttention.

## Công việc tiếp theo

1. Hoàn tất chuyển repo, chạy CPU tests và preflight trên server.
2. Xây baseline semantic CPU theo BACKLOG B01–B04, giữ split v2/holdout policy.
3. Chốt model thử nhỏ và wall-time; benchmark planner trên development bằng profile P100.
4. Chỉ cân nhắc fine-tune/quantization sau baseline, error analysis và kiểm tra backend tương thích; không giả định QLoRA/vLLM/FlashAttention chạy trên P100.

Runtime cuối BTC dùng RTX5090 theo Rule/7. Profile P100 phục vụ phát triển; cần environment/container riêng cho Blackwell theo guideline BTC và kiểm tra tái lập khi chuyển backend. Không sửa rulebook nghiệp vụ để bù giới hạn phần cứng.
