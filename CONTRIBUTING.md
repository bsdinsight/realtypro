# Contributing to Realty Pro

Cảm ơn bạn quan tâm đến Realty Pro! Một vài điểm trước khi bạn bắt đầu:

## Yêu cầu

1. **CLA (Contributor License Agreement)** — bắt buộc cho mọi contributor.
   - Bot sẽ tự yêu cầu ký khi bạn mở PR đầu tiên.
   - CLA cho phép BSDInsight dual-license code của bạn (AGPL cho Community + proprietary cho Enterprise).
2. **Mở Issue trước khi gửi PR lớn** để thảo luận thiết kế. Tránh PR bị reject do hướng tiếp cận khác.

## Code style

- **Python**: PEP 8 + Odoo guidelines. Field naming snake_case, model naming `module.entity`.
- **XML views**: indent 4 spaces, attribute order chuẩn Odoo.
- **Commit messages**: prefix theo nghiệp vụ — `fix(loan):`, `feat(progress):`, `docs:`, `chore(ci):`...
- **Test**: bắt buộc cho new feature. Sử dụng `--test-tags` của Odoo.

## Workflow

1. Fork repo
2. Tạo branch từ `main`: `git checkout -b fix/issue-123`
3. Code + add tests
4. Run CI locally:
   ```bash
   docker run --rm \
     -v $(pwd)/addons:/mnt/extra-addons \
     odoo:19 \
     --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons/_common,/mnt/extra-addons/_project \
     -d test_db -i your_module --test-enable --stop-after-init
   ```
5. Push branch, mở PR
6. CI sẽ chạy tự động — fix tất cả failures trước khi request review

## Module được accept vào Community Edition

Realty Pro Community Edition target các tính năng **foundation** cho SME / startup BĐS Việt Nam. Tính
năng nâng cao (multi-project, EVM, Bryntum Gantt, marketplace, AI) thuộc Enterprise Edition.

Trước khi propose new module, hỏi xem nó fit Community hay Enterprise. Xem [docs/license_strategy.md](docs/license_strategy.md) cho chi tiết.

## License

Code đóng góp được phân phối dưới AGPL-3.0. Khi ký CLA, bạn cấp BSDInsight quyền dual-license
code của bạn dưới license khác (proprietary) — cho phép phân phối trong Realty Pro Enterprise.

## Câu hỏi?

- Discussions: https://github.com/bsdinsight/realtypro/discussions
- Email: dev@bsdinsight.com
