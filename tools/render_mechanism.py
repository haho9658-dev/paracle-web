#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""캐스터 락 작동 원리 도식(솔루션 섹션)을 생성해 index.html · css/style.css 에 반영한다.

    python tools/render_mechanism.py            # 현재 각도 그대로 다시 생성
    python tools/render_mechanism.py 55 24      # 방위각 55도, 앙각 24도
    python tools/render_mechanism.py 55 24 --dry-run   # 파일을 고치지 않고 값만 출력

방위각(alpha)  좌우로 도는 각. 0이면 정면, 90이면 완전 측면.
               키울수록 휠체어 오른쪽이 많이 보인다.
앙각(beta)     위에서 내려다보는 각. 0이면 눈높이, 키울수록 위에서 본다.
               35도를 넘으면 정 아이소메트릭에 가까워져 뒷바퀴 두 개가
               겹치고 좌석이 뭉쳐 휠체어로 읽히지 않는다. 20~28도 권장.

────────────────────────────────────────────────────────────────────────
투영
    sx =  X·cosα + Y·sinα
    sy =  X·sinα·sinβ − Y·cosα·sinβ − Z·cosβ

  월드 X = 승강장 좌우, Y = 진행 방향(전동차 쪽), Z = 위

바퀴의 요(yaw) 회전을 3D처럼 보이게 하는 원리
  바퀴는 원판이고 굴림 방향은 d = (sinθ, cosθ, 0) 이다.
  투영이 선형이므로 원판의 정사영은 두 켤레 반지름
      A = P(d) = r·( sin(θ+α),  −sinβ·cos(θ+α) )
      B = P(z) = r·( 0, −cosβ )
  으로 정의되는 타원이 된다. 따라서 단위원에
      matrix(Ax, Ay, Bx, By, Cx, Cy)
  를 걸면 요 회전이 근사가 아니라 정확하게 재현된다.
  이 스크립트는 요각별 행렬을 뽑아 CSS keyframe 으로 내보낸다.

시점을 바꾸면 화면 좌표가 전부 달라지므로, 아래가 모두 함께 재계산된다.
  · 장면 기하(승강장·점자블록·틈·전동차·휠체어)
  · 캐스터 요 회전 keyframe 행렬과 잠금 상태의 고정 행렬
  · 전동차 진입 이동량
  · viewBox 에 맞춘 스케일과 오프셋
"""
import io
import math
import os
import re
import sys

# ─────────────────────────────────────────────── 시점
argv = [a for a in sys.argv[1:] if not a.startswith("-")]
DRY = "--dry-run" in sys.argv
ALPHA_DEG = float(argv[0]) if len(argv) > 0 else 55.0
BETA_DEG = float(argv[1]) if len(argv) > 1 else 24.0
ALPHA, BETA = math.radians(ALPHA_DEG), math.radians(BETA_DEG)
SA, CA_, SB, CB = math.sin(ALPHA), math.cos(ALPHA), math.sin(BETA), math.cos(BETA)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "index.html")
CSS = os.path.join(ROOT, "css", "style.css")

VW, VH = 440, 320           # viewBox
FILL = 0.96                 # viewBox 를 채우는 비율. 낮출수록 도식이 작아진다
TOP_PAD, BOTTOM_PAD = 12, 48    # 위 여백 · 아래 상태 문구 자리

# ─────────────────────────────────────────────── 장면 치수 (월드 단위)
PX = 145                    # 승강장 좌우 반폭 (차체 폭과 맞춘다)
PY0 = -155                  # 승강장 안쪽 끝
TY0, TY1 = -40, -14         # 점자블록
GY0, GY1 = 0, 30            # 틈
TRY = 118                   # 전동차 안쪽 끝

# 전동차 앞면 : 차체가 문보다 위로 올라가고 양옆에 창이 있어야 전동차로 읽힌다.
# 차체는 승강장(PX)보다 넓게 잡는다 — 실제로도 전동차가 더 길고, 창을 넣을 폭도 생긴다.
CAR_X = 145                 # 차체 좌우 반폭 (승강장과 맞춘다)
CAR_Z = 162                 # 차체 높이 (문 위로 올라가되 압도하지 않을 만큼)
DH, DZ = 70, 140            # 출입문 반폭 · 높이
DOOR_W = 26                 # 열린 미닫이 문짝 폭
WIN_X0, WIN_X1 = 104, 138   # 창문 좌우 (문짝 바깥)
WIN_Z0, WIN_Z1 = 88, 134    # 창문 상하
DOOR_GLASS = (6, 74, 128)   # 문 유리 : 문짝 테두리 여백, 아래, 위

# 휠체어 (로컬 좌표, +Y 가 진행 방향, 원점은 뒷바퀴 접지 중앙)
RW_R, RW_X, RW_Y = 42, 46, -10          # 뒷바퀴
CA_R, CA_X, CA_Y = 16, 27, 48           # 앞 캐스터
PIVOT_Z = 52
SEAT_Z, BACK_Y, BACK_Z = 60, -36, 128

CHAIR_Y = -66               # 시작 위치 (틈 앞)
ENTER_DY = 118              # 잠금 시 전동차로 들어가는 거리

YAW_SEQ = [0, 14, 28, 40, 30, 12, 0, -10, -18, -24, -16, -6, 0]   # 자유 회전 한 바퀴


# ─────────────────────────────────────────────── 투영
def P(x, y, z):
    return (x * CA_ + y * SA, x * SA * SB - y * CA_ * SB - z * CB)


def wheel_matrix(cx, cy, cz, r, yaw_deg):
    """중심 (cx,cy,cz), 반지름 r, 요각 yaw 인 원판 → 단위원에 걸 matrix 6요소"""
    t = math.radians(yaw_deg) + ALPHA
    return (r * math.sin(t), -r * SB * math.cos(t), 0.0, -r * CB) + P(cx, cy, cz)


def n(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def n1(v):
    return ("%.1f" % v).rstrip("0").rstrip(".")


def mstr(m, sep=" "):
    return "matrix(%s)" % sep.join(n(v) for v in m)


def poly(pts):
    return " ".join(("M" if i == 0 else "L") + "%s %s" % tuple(n(c) for c in P(*p))
                    for i, p in enumerate(pts)) + " Z"


def seg(p1, p2):
    return "M%s %s L%s %s" % (n(P(*p1)[0]), n(P(*p1)[1]), n(P(*p2)[0]), n(P(*p2)[1]))


# ─────────────────────────────────────────────── 장면
parts = []
add = parts.append

add('<!-- 승강장 -->')
add('<path d="%s" fill="#0A3159" stroke="#ffffff" stroke-opacity=".2" stroke-width="1.5"/>'
    % poly([(-PX, PY0, 0), (PX, PY0, 0), (PX, GY0, 0), (-PX, GY0, 0)]))

add('<!-- 점자블록 -->')
add('<path d="%s" fill="#E5C15A" fill-opacity=".4" stroke="none"/>'
    % poly([(-PX, TY0, 0), (PX, TY0, 0), (PX, TY1, 0), (-PX, TY1, 0)]))
dots = []
x = -PX + 14
while x < PX - 6:
    sx, sy = P(x, (TY0 + TY1) / 2.0, 0)
    dots.append('<ellipse cx="%s" cy="%s" rx="3.6" ry="1.6"/>' % (n(sx), n(sy)))
    x += 24
add('<g fill="#E5C15A" fill-opacity=".85" stroke="none">%s</g>' % "".join(dots))

add('<!-- 틈 -->')
add('<path d="%s" fill="#02182E" stroke="#88CED6" stroke-opacity=".45" stroke-width="1.5"/>'
    % poly([(-PX, GY0, 0), (PX, GY0, 0), (PX, GY1, 0), (-PX, GY1, 0)]))

add('<!-- 전동차 바닥 -->')
add('<path d="%s" fill="#0C3A66" stroke="#ffffff" stroke-opacity=".2" stroke-width="1.5"/>'
    % poly([(-PX, GY1, 0), (PX, GY1, 0), (PX, TRY, 0), (-PX, TRY, 0)]))

add('<!-- 전동차 앞면 : 차체 · 창문 · 출입문 -->')
# 차체 벽 (문을 뺀 세 조각 : 좌 · 우 · 문 위)
add('<g class="iso-carbody" fill="#08294A" fill-opacity=".55" stroke="#ffffff" '
    'stroke-opacity=".18" stroke-width="1.5" stroke-linejoin="round">'
    '<path d="%s"/><path d="%s"/><path d="%s"/></g>'
    % (poly([(-CAR_X, GY1, 0), (-DH, GY1, 0), (-DH, GY1, CAR_Z), (-CAR_X, GY1, CAR_Z)]),
       poly([(DH, GY1, 0), (CAR_X, GY1, 0), (CAR_X, GY1, CAR_Z), (DH, GY1, CAR_Z)]),
       poly([(-DH, GY1, DZ), (DH, GY1, DZ), (DH, GY1, CAR_Z), (-DH, GY1, CAR_Z)])))

# 창문 (열린 문짝 바깥쪽)
add('<g class="iso-carwindow" fill="#123E6B" fill-opacity=".95" stroke="#88CED6" '
    'stroke-opacity=".4" stroke-width="2" stroke-linejoin="round">'
    '<path d="%s"/><path d="%s"/></g>'
    % (poly([(-WIN_X1, GY1, WIN_Z0), (-WIN_X0, GY1, WIN_Z0),
             (-WIN_X0, GY1, WIN_Z1), (-WIN_X1, GY1, WIN_Z1)]),
       poly([(WIN_X0, GY1, WIN_Z0), (WIN_X1, GY1, WIN_Z0),
             (WIN_X1, GY1, WIN_Z1), (WIN_X0, GY1, WIN_Z1)])))

# 열린 미닫이문 : 문틀 바깥으로 물러난 문짝과 그 유리
_g, _z0, _z1 = DOOR_GLASS
add('<g class="iso-cardoor" fill="#0B3A66" fill-opacity=".95" stroke="#88CED6" '
    'stroke-opacity=".5" stroke-width="2" stroke-linejoin="round">'
    '<path d="%s"/><path d="%s"/></g>'
    % (poly([(-DH - DOOR_W, GY1, 0), (-DH, GY1, 0), (-DH, GY1, DZ), (-DH - DOOR_W, GY1, DZ)]),
       poly([(DH, GY1, 0), (DH + DOOR_W, GY1, 0), (DH + DOOR_W, GY1, DZ), (DH, GY1, DZ)])))
add('<g class="iso-cardoor-glass" fill="#1A5A9B" fill-opacity=".95" stroke="#88CED6" '
    'stroke-opacity=".35" stroke-width="1.5" stroke-linejoin="round">'
    '<path d="%s"/><path d="%s"/></g>'
    % (poly([(-DH - DOOR_W + _g, GY1, _z0), (-DH - _g, GY1, _z0),
             (-DH - _g, GY1, _z1), (-DH - DOOR_W + _g, GY1, _z1)]),
       poly([(DH + _g, GY1, _z0), (DH + DOOR_W - _g, GY1, _z0),
             (DH + DOOR_W - _g, GY1, _z1), (DH + _g, GY1, _z1)])))

# 출입문 개구부 테두리 · 차체 윗선
add('<g fill="none" stroke="#88CED6" stroke-opacity=".65" stroke-width="3.4" stroke-linecap="round">'
    '<path d="%s"/><path d="%s"/><path d="%s"/></g>'
    % (seg((-DH, GY1, 0), (-DH, GY1, DZ)), seg((DH, GY1, 0), (DH, GY1, DZ)),
       seg((-DH, GY1, DZ), (DH, GY1, DZ))))
add('<path d="%s" fill="none" stroke="#ffffff" stroke-opacity=".28" stroke-width="2.5" '
    'stroke-linecap="round"/>' % seg((-CAR_X, GY1, CAR_Z), (CAR_X, GY1, CAR_Z)))


def chair():
    """깊이 순서대로 그린다: 먼 쪽 뒷바퀴 → 차체 → 가까운 쪽 뒷바퀴 → 앞바퀴.
    좌석·등받이를 불투명 면으로 두어 뒤쪽 요소를 가리게 한다."""
    e = []

    def rear(sgn, dim):
        cx, cy, cz = sgn * RW_X, RW_Y, RW_R
        op, rim = (".5", ".25") if dim else ("1", ".45")
        hx, hy = P(cx, cy, cz)
        return ('<g><circle r="1" transform="%s" fill="#0A3159" fill-opacity=".6" stroke="#ffffff" '
                'stroke-opacity="%s" stroke-width="4.5" vector-effect="non-scaling-stroke"/>'
                '<circle r="1" transform="%s" fill="none" stroke="#ffffff" stroke-opacity="%s" '
                'stroke-width="2" vector-effect="non-scaling-stroke"/>'
                '<circle cx="%s" cy="%s" r="4" fill="#88CED6" fill-opacity="%s"/></g>'
                % (mstr(wheel_matrix(cx, cy, cz, RW_R, 0)), op,
                   mstr(wheel_matrix(cx, cy, cz, RW_R * 0.7, 0)), rim, n(hx), n(hy), op))

    e.append(rear(-1, True))

    e.append('<path d="%s" fill="#17548C" stroke="#ffffff" stroke-opacity=".85" '
             'stroke-width="3.6" stroke-linejoin="round"/>'
             % poly([(-38, BACK_Y, SEAT_Z), (38, BACK_Y, SEAT_Z),
                     (38, BACK_Y, BACK_Z), (-38, BACK_Y, BACK_Z)]))
    e.append('<path d="%s" fill="#1E68AB" stroke="#ffffff" stroke-opacity=".85" '
             'stroke-width="3.6" stroke-linejoin="round"/>'
             % poly([(-38, BACK_Y, SEAT_Z), (38, BACK_Y, SEAT_Z),
                     (38, 28, SEAT_Z), (-38, 28, SEAT_Z)]))

    fr = []
    L = lambda a, b: fr.append('<path d="%s"/>' % seg(a, b))
    for sx in (-30, 30):                                        # 손잡이
        L((sx, BACK_Y, BACK_Z), (sx, BACK_Y - 16, BACK_Z + 16))
    for sx in (-40, 40):                                        # 팔걸이
        L((sx, -26, 92), (sx, 20, 92))
        L((sx, -26, 92), (sx, -26, SEAT_Z))
        L((sx, 20, 92), (sx, 20, SEAT_Z))
    for s in (-1, 1):                                           # 프레임
        L((s * 36, -22, SEAT_Z), (s * RW_X, RW_Y, RW_R))
        L((s * 36, 24, SEAT_Z), (s * CA_X, CA_Y, PIVOT_Z))
        L((s * CA_X, CA_Y, PIVOT_Z), (s * CA_X, CA_Y, CA_R + 4))
    L((-26, 80, 22), (26, 80, 22))                              # 발판
    for s in (-1, 1):
        L((s * CA_X, CA_Y, 42), (s * 26, 80, 22))
    e.append('<g fill="none" stroke="#ffffff" stroke-opacity=".85" stroke-width="4.5" '
             'stroke-linecap="round">%s</g>' % "".join(fr))

    e.append(rear(1, False))

    ARC_W, ARC_H, ARC_DY = 15, 11, 4    # 회전 화살표 폭 · 굽은 높이 · 아래 처짐
    FWD_Y = 26                          # 캐스터 진행 방향(+Y) 쪽으로 띄우는 거리
    SWIVEL_Z = 2                        # 바퀴 중심이 아니라 바닥에 거의 붙는 높이
    SWIVEL_COLOR = "#F0A9A9"            # 캐스터 색(#88CED6)과 구분되는 경고색 — FREE 상태 문구와 같은 색
    SWIVEL_TILT = 30                    # 화살표 자체를 시계 방향으로 추가로 기울이는 각(도)
    FIX_COLOR = "#A9DDE3"               # LOCKED 상태 문구와 같은 색
    FIX_SCALE = 0.62                    # 자물쇠 아이콘 축소 비율 (원본은 24x24 아이콘 좌표계)
    # 사이트 다른 곳(순간 잠금 메커니즘 카드)과 같은 자물쇠 도형을 재사용한다.
    LOCK_GLYPH = ('<path d="M7 11V8a5 5 0 0 1 10 0v3" fill="none" stroke="%s" stroke-width="4.2" '
                  'stroke-linecap="round" stroke-linejoin="round"/>'
                  '<rect x="4" y="11" width="16" height="10" rx="2" fill="none" stroke="%s" '
                  'stroke-width="4.2" stroke-linejoin="round"/>'
                  '<circle cx="12" cy="16" r="1.6" fill="%s"/>')
    LOCK_CX, LOCK_CY = 12, 14.5         # 아이콘 원본 좌표계에서의 중심(가로 4~20, 세로 8~21)
    for s, tag in ((-1, "a"), (1, "b")):                        # 앞 캐스터
        lx, ly = P(s * CA_X, CA_Y + FWD_Y, SWIVEL_Z)            # 바퀴 앞(진행 방향), 바닥에 가까운 높이
        x0, y0 = lx - ARC_W, ly + ARC_DY
        x1, y1 = lx + ARC_W, ly + ARC_DY
        cx_, cy_ = lx, ly - ARC_H
        ang0 = math.degrees(math.atan2(y0 - cy_, x0 - cx_))    # 왼쪽 화살촉 : 곡선의 접선 반대 방향
        ang1 = math.degrees(math.atan2(y1 - cy_, x1 - cx_))    # 오른쪽 화살촉 : 곡선의 접선 방향
        # 좌우로 오가는 요 회전을 표현하는 휘어진 양방향 화살표.
        # 평상시(자유 회전)에는 보이고, 잠기면 사라진다 — .iso-swivel CSS 참고.
        # 전체를 자기 중심(lx, ly) 기준으로 SWIVEL_TILT도 만큼 시계 방향 회전.
        e.append('<g class="iso-swivel" transform="rotate(%s %s %s)">'
                 '<path d="M%s %s Q%s %s %s %s" fill="none" stroke="%s" stroke-width="2.6" '
                 'stroke-linecap="round"/>'
                 '<path d="M-6 -5 L0 0 L-6 5" fill="none" stroke="%s" stroke-width="2.6" '
                 'stroke-linecap="round" stroke-linejoin="round" transform="translate(%s %s) rotate(%s)"/>'
                 '<path d="M-6 -5 L0 0 L-6 5" fill="none" stroke="%s" stroke-width="2.6" '
                 'stroke-linecap="round" stroke-linejoin="round" transform="translate(%s %s) rotate(%s)"/>'
                 '</g>'
                 % (n1(SWIVEL_TILT), n(lx), n(ly),
                    n(x0), n(y0), n(cx_), n(cy_), n(x1), n(y1), SWIVEL_COLOR,
                    SWIVEL_COLOR, n(x0), n(y0), n1(ang0),
                    SWIVEL_COLOR, n(x1), n(y1), n1(ang1)))
        # 잠금 시 : 같은 자리에서 앞바퀴가 잠겨 있음을 자물쇠 모양으로
        # 보여준다. 평상시엔 숨고 잠기면 나타난다 — iso-swivel과 정반대
        # — .iso-fixed CSS 참고. "순간 잠금 메커니즘" 카드와 같은 도형.
        ftx = lx - LOCK_CX * FIX_SCALE
        fty = ly - LOCK_CY * FIX_SCALE
        e.append('<g class="iso-fixed" transform="translate(%s %s) scale(%s)">%s</g>'
                 % (n(ftx), n(fty), n(FIX_SCALE), LOCK_GLYPH % (FIX_COLOR, FIX_COLOR, FIX_COLOR)))
        e.append('<circle class="iso-caster iso-caster-%s" r="1" transform="%s" fill="#0A3159" '
                 'fill-opacity=".75" stroke="#ffffff" stroke-width="4.2" '
                 'vector-effect="non-scaling-stroke"/>'
                 % (tag, mstr(wheel_matrix(s * CA_X, CA_Y, CA_R, CA_R, 0))))
        hx, hy = P(s * CA_X, CA_Y, CA_R)
        e.append('<circle cx="%s" cy="%s" r="3" fill="#88CED6"/>' % (n(hx), n(hy)))

    lx, ly = P(40, 20, 92)                                      # 레버
    ex, ey = n(lx + 20), n(ly - 16)
    e.append('<g class="mech-lever" id="mechLever" style="transform-origin:%spx %spx">'
             '<path d="M%s %s L%s %s" fill="none" stroke="#88CED6" stroke-width="4.5" '
             'stroke-linecap="round"/><circle cx="%s" cy="%s" r="5.5" fill="#88CED6"/></g>'
             % (n(lx), n(ly), n(lx), n(ly), ex, ey, ex, ey))
    # 레버 옆 라벨 — id="mechLeverLabel" 을 js/main.js 가 그대로 찾아 "레버 해제"/"레버 잠금"으로
    # 갈아 끼운다. 이 id가 없으면 main.js 가 null.textContent 에서 예외를 던지고,
    # 그 뒤에 나오는 코드(문의 폼 검증·제출 처리 등)가 통째로 실행되지 않는다.
    e.append('<text x="%s" y="%s" id="mechLeverLabel" class="mech-label" '
             'text-anchor="start">레버 해제</text>' % (n(lx + 30), n(ly - 12)))
    return "".join(e)


base = P(0, CHAIR_Y, 0)
add('<g transform="translate(%s %s)"><g class="mech-chair" id="mechChair">%s</g></g>'
    % (n(base[0]), n(base[1]), chair()))
body = "\n          ".join(parts)

# ─────────────────────────────────────────────── viewBox 자동 맞춤
corners = [(-PX, PY0, 0), (PX, PY0, 0), (PX, TRY, 0), (-PX, TRY, 0),
           (-CAR_X, GY1, 0), (CAR_X, GY1, 0),
           (-CAR_X, GY1, CAR_Z), (CAR_X, GY1, CAR_Z),
           (0, CHAIR_Y + BACK_Y - 16, BACK_Z + 16)]
xs = [P(*c)[0] for c in corners]
ys = [P(*c)[1] for c in corners]
bw, bh = max(xs) - min(xs), max(ys) - min(ys)
avail_h = VH - TOP_PAD - BOTTOM_PAD
S = min((VW - 26) / bw, avail_h / bh) * FILL
OX = (VW - bw * S) / 2.0 - min(xs) * S
OY = TOP_PAD + (avail_h - bh * S) / 2.0 - min(ys) * S


def scr(x, y, z):
    sx, sy = P(x, y, z)
    return (sx * S + OX, sy * S + OY)


# ─────────────────────────────────────────────── 라벨 · 진행 방향
labels = []
# 승강장 라벨은 넣지 않는다 — 노란 점자블록이 이미 승강장임을 말해주고,
# 휠체어·승강장 경계선과 겹쳐 지저분해진다.
for w, txt, cls, anchor in [((112, 18, 0), "틈", "mech-gaplabel", "start"),
                            ((104, 96, 4), "전동차", "mech-caption", "middle")]:
    sx, sy = scr(*w)
    fill = '#88CED6" font-weight="700' if cls == "mech-gaplabel" else '#ffffff" fill-opacity=".5'
    labels.append('<text x="%s" y="%s" class="%s" text-anchor="%s" fill="%s" font-size="12">%s</text>'
                  % (n1(sx), n1(sy), cls, anchor, fill, txt))

a0, a1 = scr(-132, -148, 2), scr(-132, -88, 2)
ang = math.degrees(math.atan2(a1[1] - a0[1], a1[0] - a0[0]))
ax, ay = scr(-146, -114, 30)
arrow = ('<g class="mech-axis" fill="none" stroke="#ffffff" stroke-opacity=".3">'
         '<path d="M%s %s L%s %s" stroke-width="2" stroke-dasharray="6 8"/>'
         '<path d="M-7 -6 L0 0 L-7 6" transform="translate(%s %s) rotate(%s)" stroke-width="2.5" '
         'stroke-linecap="round" stroke-linejoin="round"/></g>'
         '<text x="%s" y="%s" class="mech-caption" text-anchor="middle" fill="#ffffff" '
         'fill-opacity=".45" font-size="12">진행 방향</text>'
         % (n1(a0[0]), n1(a0[1]), n1(a1[0]), n1(a1[1]), n1(a1[0]), n1(a1[1]), n1(ang),
            n1(ax), n1(ay)))

svg = "\n".join([
    '        <!-- 캐스터 락 작동 원리 도식 — tools/render_mechanism.py 가 생성한다.',
    '             직접 손대지 말고 스크립트를 다시 돌릴 것.',
    '             카메라 방위각 %g도 · 앙각 %g도 축측투영.' % (ALPHA_DEG, BETA_DEG),
    '             바퀴 원판의 요 회전은 matrix() 정사영으로 재현하므로 실제 3D처럼 돈다. -->',
    '        <svg class="mech-svg" id="mechSvg" viewBox="0 0 %d %d" role="img"' % (VW, VH),
    '             aria-label="캐스터 락 작동 원리 도식 — 휠체어가 지하철 승강장에서 전동차로 '
    '들어가는 모습을 오른쪽 대각선 위에서 본 그림. 잠금을 풀면 앞바퀴가 제멋대로 돌아 틈 앞에서 '
    '멈추고, 잠그면 직진으로 고정되어 전동차 안으로 들어간다.">',
    '          <g class="mech-scene" transform="translate(%s %s) scale(%s)">'
    % (n1(OX), n1(OY), ("%.3f" % S).rstrip("0").rstrip(".")),
    '          ' + body,
    '          </g>',
    '          ' + arrow,
] + ['          ' + l for l in labels] + [
    '          <text x="220" y="308" class="mech-status-free" text-anchor="middle"',
    '                fill="#F0A9A9" font-size="13" font-weight="700">'
    '바퀴 방향 불안정 → 틈 앞에서 걸림·전복 위험</text>',
    '          <text x="220" y="308" class="mech-status-lock" text-anchor="middle"',
    '                fill="#A9DDE3" font-size="13" font-weight="700" opacity="0">'
    '바퀴 방향 고정 → 틈을 건너 전동차로 승차</text>',
    '        </svg>',
])

# ─────────────────────────────────────────────── CSS keyframe · 잠금 행렬 · 진입 이동량
kf = []
for tag, s in (("A", -1), ("B", 1)):
    kf.append("@keyframes isoCaster%s {" % tag)
    last = len(YAW_SEQ) - 1
    for i, yaw in enumerate(YAW_SEQ):
        pct = "0%" if i == 0 else ("100%" if i == last else "%.4g%%" % (i * 100.0 / last))
        kf.append("  %-8s { transform: %s; }"
                  % (pct, mstr(wheel_matrix(s * CA_X, CA_Y, CA_R, CA_R, yaw), ", ")))
    kf.append("}")
    kf.append("")
kf_css = "\n".join(kf).rstrip()

ent = P(0, CHAIR_Y + ENTER_DY, 0)
DX, DY = ent[0] - base[0], ent[1] - base[1]

print("방위각 %g도 · 앙각 %g도" % (ALPHA_DEG, BETA_DEG))
print("  스케일 %.3f  오프셋 (%.1f, %.1f)" % (S, OX, OY))
print("  전동차 진입 이동량 (%.2f, %.2f)" % (DX, DY))
print("  잠금 행렬 A %s" % mstr(wheel_matrix(-CA_X, CA_Y, CA_R, CA_R, 0), ", "))
print("  잠금 행렬 B %s" % mstr(wheel_matrix(CA_X, CA_Y, CA_R, CA_R, 0), ", "))

if DRY:
    print("--dry-run : 파일은 고치지 않았습니다.")
    raise SystemExit

# ─────────────────────────────────────────────── 파일 반영
html = io.open(HTML, encoding="utf-8").read()
m = re.search(r"[ ]*<!-- 캐스터 락 작동 원리 도식.*?</svg>", html, re.S)
if not m:      # 이전 세대 주석까지 받아준다
    m = re.search(r"[ ]*<!-- (?:3/4 시점|아이소메트릭).*?</svg>", html, re.S)
if not m:
    raise SystemExit("index.html 에서 도식 SVG 블록을 찾지 못했습니다.")
io.open(HTML, "w", encoding="utf-8").write(html[:m.start()] + svg + html[m.end():])

css = io.open(CSS, encoding="utf-8").read()
css, cnt = re.subn(r"@keyframes isoCasterA \{.*?\n\}\n\n@keyframes isoCasterB \{.*?\n\}",
                   kf_css, css, flags=re.S)
if cnt != 1:
    raise SystemExit("style.css 에서 isoCaster keyframes 를 찾지 못했습니다.")
for tag, s in (("a", -1), ("b", 1)):
    css, c2 = re.subn(
        r"\.mech-svg\.is-locked \.iso-caster-%s \{ animation: none; transform: matrix\([^)]*\); \}" % tag,
        ".mech-svg.is-locked .iso-caster-%s { animation: none; transform: %s; }"
        % (tag, mstr(wheel_matrix(s * CA_X, CA_Y, CA_R, CA_R, 0), ", ")), css)
    if c2 != 1:
        raise SystemExit("style.css 에서 iso-caster-%s 잠금 규칙을 찾지 못했습니다." % tag)
css, c3 = re.subn(r"84%, 100% \{ transform: translate\([^)]*\); \}",
                  "84%%, 100%% { transform: translate(%.2fpx, %.2fpx); }" % (DX, DY), css)
if c3 != 1:
    raise SystemExit("style.css 에서 isoEnter 종료 키프레임을 찾지 못했습니다.")
for pct, k in (("30%", 0.085), ("45%", 0.11), ("60%", 0.085)):
    css = re.sub(r"  %s      \{ transform: translate\([^)]*\); \}" % re.escape(pct),
                 "  %s      { transform: translate(%.2fpx, %.2fpx); }" % (pct, DX * k, DY * k), css)
io.open(CSS, "w", encoding="utf-8").write(css)

print("index.html · css/style.css 에 반영했습니다.")
print("css/js 캐시 버전(?v=) 을 올리는 것을 잊지 마세요.")
