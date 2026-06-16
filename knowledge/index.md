---
okf_version: "0.1"
---

# AutoStock Knowledge

이 번들은 AutoStock 저장소의 첫 OKF 지식 계층이다. 현재 문서는 저장소 근거로 구성한 초기 초안이며, 프로젝트 소유자의 리뷰 전까지 권위 있는 사양으로 보지 않는다.

## Categories

* [Architecture](architecture/index.md) - 시스템 경계와 배치 실행 구조를 설명한다.
* [Components](components/index.md) - 핵심 수집기, 엔진, 리포팅 구성요소의 책임을 설명한다.
* [Interfaces](interfaces/index.md) - CLI, 설정, 런타임 산출물 계약을 설명한다.
* [Domain](domain/index.md) - 후보 검토, 매크로 정책, 제외 사유의 도메인 규칙을 설명한다.
* [Persistence](persistence/index.md) - 로컬 JSON 산출물과 캐시의 저장 규칙을 설명한다.
* [Development](development/index.md) - 로컬 개발과 QA 게이트를 설명한다.
* [Operations](operations/index.md) - 실행, smoke, 향후 운영 안정화 범위를 설명한다.
* [Security](security/index.md) - credential, 개인정보, readonly 경계를 설명한다.
* [Decisions](decisions/index.md) - 현재 단계에서 수용된 제품/기술 결정을 설명한다.

## Open questions

* OKF 문서의 장기 소유자 또는 리뷰 책임자는 저장소 근거에서 확인되지 않았다.
* v0.2 최종 릴리스 전후에 일부 상태 문서와 코드의 표현이 달라질 수 있으므로 리뷰가 필요하다.
