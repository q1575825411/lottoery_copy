from __future__ import annotations

from .analysis import omit, omit_dict
from .constants import MAX_DRAWS, RED_BALL_COUNT, RED_BALL_MAX
from .deps import ExcelDeps
from .patterns import detect_flag_range_hits, detect_n_bottom_hits, detect_pile_hits, detect_re_pile_hits, detect_trend_reverse_hits
from .state import LottoState


class WorkbookBuilder:
    def __init__(self, deps: ExcelDeps, state: LottoState) -> None:
        self.deps = deps
        self.state = state
        self.workbook = None

    def apply_xls_font(self, ws) -> None:
        row_num = ws.max_row
        for col in "ABCDEFGHIJKMNOPQRSTU":
            ws[f"{col}{row_num}"].font = self.deps.font_bold
        ws[f"L{row_num}"].font = self.deps.font_red

    def create_workbook(self):
        workbook = self.deps.Workbook()
        default_sheet = workbook.active
        workbook.remove(default_sheet)

        ws0 = workbook.create_sheet(title="文件信息", index=0)
        ws0["A1"] = "最新更新期数"

        ws1 = workbook.create_sheet(title="奇偶数表", index=1)

        ws2 = workbook.create_sheet(title="大小数表", index=2)

        ws3 = workbook.create_sheet(title="和值偏差表", index=3)
        ws3.append(["日期", "期数", "和值", "020", "030", "040", "050", "060", "070", "080", "090", "100", "110", "120", "130", "140", "150", "160", "170", "180", "190"])
        self.apply_xls_font(ws3)

        ws4 = workbook.create_sheet(title="区间表", index=4)
        ws4.append(["日期", "期数", "1-5", "6-10", "11-15", "16-20", "21-25", "26-30", "31-33"])
        self.apply_xls_font(ws4)

        ws5 = workbook.create_sheet(title="百分比表", index=5)
        ws5.append(["日期", "期数", "热号", "冷号", "温号"])
        self.apply_xls_font(ws5)

        ws6 = workbook.create_sheet(title="遗漏表", index=6)
        ws6.append(["日期", "期数", "中奖号码", "遗漏情况", "遗漏少于10次的个数", "总计", "平均"])
        self.apply_xls_font(ws6)

        ws7 = workbook.create_sheet(title="遗漏数字偏差表", index=7)

        ws8 = workbook.create_sheet(title="中期表", index=8)

        ws9 = workbook.create_sheet(title="原始数据", index=9)
        ws9.append(["期号", "开奖日期", "红1", "红2", "红3", "红4", "红5", "红6", "蓝球"])
        self.apply_xls_font(ws9)

        return workbook

    def sync_raw_data(self) -> None:
        ws = self.workbook["原始数据"]
        if ws.max_row > 1:
            ws.delete_rows(2, ws.max_row - 1)

        for idx, serial in enumerate(self.state.serials[:MAX_DRAWS]):
            row = [
                serial,
                self.state.draw_dates[idx],
                *self.state.red_balls[idx][:RED_BALL_COUNT],
                self.state.blue_balls[idx],
            ]
            ws.append(row)

    def file_odd_or_even(self, ws) -> None:
        state = self.state
        ws.append([""])
        ws.append([state.draw_dates[state.start_serial] + state.serials[state.start_serial]])
        self.apply_xls_font(ws)
        self.odd_or_even(ws, 10)
        self.odd_or_even(ws, 5)
        self.odd_or_even(ws, 1)

    def odd_or_even(self, ws, draw_count: int) -> None:
        state = self.state
        odd = 0
        even = 0
        for i in range(state.start_serial, state.start_serial + draw_count):
            for j in range(RED_BALL_COUNT):
                if state.red_balls[i][j] % 2 == 0:
                    even += 1
                else:
                    odd += 1

        if draw_count != 1:
            if even > odd:
                ws.append(["近%d期有" % draw_count, "奇=%d，偶=%d" % (odd, even), "偶+%d" % (even - odd)])
            elif even < odd:
                ws.append(["近%d期有" % draw_count, "奇=%d，偶=%d" % (odd, even), "奇+%d" % (odd - even)])
            else:
                ws.append(["近%d期有" % draw_count, "奇=%d，偶=%d" % (odd, even), "奇=偶"])
        else:
            ws.append(["本期奇偶比例:", "奇 : 偶 = %d : %d" % (odd, even)])
        self.apply_xls_font(ws)

    def file_big_or_small(self, ws) -> None:
        state = self.state
        ws.append([""])
        ws.append([state.draw_dates[state.start_serial] + state.serials[state.start_serial]])
        self.apply_xls_font(ws)
        self.big_or_small(ws, 10)
        self.big_or_small(ws, 5)
        self.big_or_small(ws, 1)

    def big_or_small(self, ws, draw_count: int) -> None:
        state = self.state
        big = 0
        small = 0
        for i in range(state.start_serial, state.start_serial + draw_count):
            for j in range(RED_BALL_COUNT):
                if state.red_balls[i][j] <= 16:
                    small += 1
                else:
                    big += 1

        if draw_count != 1:
            if small > big:
                ws.append(["近%d期有" % draw_count, "大=%d，小=%d" % (big, small), "小+%d" % (small - big)])
            elif small < big:
                ws.append(["近%d期有" % draw_count, "大=%d，小=%d" % (big, small), "大+%d" % (big - small)])
            else:
                ws.append(["近%d期有" % draw_count, "大=%d，小=%d" % (big, small), "大=小"])
        else:
            ws.append(["本期大小比例:", "大 : 小 = %d : %d" % (big, small)])
        self.apply_xls_font(ws)

    def sum_offset(self, ws) -> None:
        state = self.state
        total = 0
        for i in range(RED_BALL_COUNT):
            total += state.red_balls[state.start_serial][i]
        cells = ["" for _ in range(21)]
        cells[0] = state.draw_dates[state.start_serial]
        cells[1] = state.serials[state.start_serial]
        cells[2] = str(total)
        cells[11] = "+"

        place = total // 10
        if place > 10:
            for i in range(12, place + 2):
                cells[i] = "+"
        elif place < 10:
            for i in range(place + 1, 11):
                cells[i] = "+"
        ws.append(cells)
        self.apply_xls_font(ws)

    def file_omit(self, ws) -> None:
        state = self.state
        cells = ["  " for _ in range(7)]
        cells[0] = state.draw_dates[state.start_serial]
        cells[1] = state.serials[state.start_serial]
        for i in range(RED_BALL_COUNT):
            cells[2] += "  %02d" % state.red_balls[state.start_serial][i]

        omitted = omit(state, state.start_serial)
        omit_num = 0
        omit_sum = 0
        for i in range(RED_BALL_COUNT):
            if omitted[i] < 10:
                omit_num += 1
            cells[3] += "  %02d" % omitted[i]
            omit_sum += omitted[i]

        cells[4] = str(omit_num)
        cells[5] = str(omit_sum)
        cells[6] = "%.1f" % (omit_sum / 6.0)
        ws.append(cells)
        self.apply_xls_font(ws)

        row_num = ws.max_row
        if ws[f"E{row_num}"].value == "6":
            ws[f"E{row_num}"].font = self.deps.font_red

    def ball_range(self, ws) -> None:
        state = self.state
        cells = ["" for _ in range(9)]
        cells[0] = state.draw_dates[state.start_serial]
        cells[1] = state.serials[state.start_serial]

        ranges = [0 for _ in range(7)]
        for i in range(RED_BALL_COUNT):
            ball = state.red_balls[state.start_serial][i]
            if 1 <= ball <= 5:
                ranges[0] += 1
            elif 6 <= ball <= 10:
                ranges[1] += 1
            elif 11 <= ball <= 15:
                ranges[2] += 1
            elif 16 <= ball <= 20:
                ranges[3] += 1
            elif 21 <= ball <= 25:
                ranges[4] += 1
            elif 26 <= ball <= 30:
                ranges[5] += 1
            elif 31 <= ball <= 33:
                ranges[6] += 1

        for i in range(7):
            cells[i + 2] = "-" if ranges[i] == 0 else str(ranges[i])
        ws.append(cells)
        self.apply_xls_font(ws)

    def hot_or_cold(self, ws) -> None:
        state = self.state
        nums = [0 for _ in range(33)]
        cells = ["" for _ in range(5)]
        cells[0] = state.draw_dates[state.start_serial]
        cells[1] = state.serials[state.start_serial]
        for i in range(state.start_serial, state.start_serial + 5):
            for j in range(RED_BALL_COUNT):
                if nums[state.red_balls[i][j] - 1] == 0:
                    nums[state.red_balls[i][j] - 1] = 1
        for i in range(state.start_serial + 5, state.start_serial + 10):
            for j in range(RED_BALL_COUNT):
                if nums[state.red_balls[i][j] - 1] == 0:
                    nums[state.red_balls[i][j] - 1] = 2
                elif nums[state.red_balls[i][j] - 1] == 1:
                    nums[state.red_balls[i][j] - 1] = 3

        hot = "  "
        cold = "  "
        warm = "  "
        for i in range(33):
            if nums[i] == 0:
                cold += "  %02d" % (i + 1)
            elif nums[i] == 3:
                hot += "  %02d" % (i + 1)
            else:
                warm += "  %02d" % (i + 1)

        cells[2] = hot
        cells[3] = cold
        cells[4] = warm
        ws.append(cells)
        self.apply_xls_font(ws)

    def omit_offset(self, ws, draw_count: int) -> None:
        state = self.state
        red_str = "".join("%02d " % state.red_balls[state.start_serial][i] for i in range(RED_BALL_COUNT))
        ws.append(["过去%d期" % draw_count, "", "本期中奖号码: %s" % red_str])
        self.apply_xls_font(ws)
        ws.append(["遗漏次数", "符合个数", "符合数字"])
        self.apply_xls_font(ws)

        omitted = {}
        for i in range(state.start_serial + draw_count - 1, state.start_serial - 1, -1):
            omit_dict(state, i, omitted)
        grouped = [[] for _ in range(RED_BALL_COUNT)]
        counts = {}
        for i in range(RED_BALL_COUNT):
            for key, value in omitted.items():
                if value == i:
                    grouped[i].append(key)
            counts[i] = len(grouped[i])
        dict_count = sorted(counts.items(), key=lambda item: item[1], reverse=False)

        for i in range(RED_BALL_COUNT):
            digits = "  "
            for j in range(1, RED_BALL_MAX + 1):
                if state.omit_table[state.start_serial][j] == dict_count[i][0]:
                    digits += "  %02d" % j
            ws.append([dict_count[i][0], dict_count[i][1], digits])
            self.apply_xls_font(ws)

    def color_omit_offset(self, ws, draw_count: int) -> None:
        state = self.state
        if state.start_serial >= 49:
            return

        state.start_serial += 1
        row_num = ws.max_row - 15
        omitted = {}
        for i in range(state.start_serial + draw_count - 1, state.start_serial - 1, -1):
            omit_dict(state, i, omitted)
        grouped = [[] for _ in range(RED_BALL_COUNT)]
        counts = {}
        for i in range(RED_BALL_COUNT):
            for key, value in omitted.items():
                if value == i:
                    grouped[i].append(key)
            counts[i] = len(grouped[i])
        dict_count = sorted(counts.items(), key=lambda item: item[1], reverse=False)

        for i in range(RED_BALL_COUNT):
            red_str = ""
            for j in range(1, RED_BALL_MAX + 1):
                if state.omit_table[state.start_serial][j] == dict_count[i][0]:
                    for cnt_index in range(RED_BALL_COUNT):
                        if j == state.red_balls[state.start_serial - 1][cnt_index]:
                            red_str += "%02d  " % j
            ws[f"F{row_num}"].font = self.deps.font_red
            ws[f"F{row_num}"].value = red_str
            row_num += 1

        state.start_serial -= 1

    def file_omit_offset(self, ws) -> None:
        state = self.state
        ws.append([""])
        ws.append([state.draw_dates[state.start_serial] + state.serials[state.start_serial]])
        self.apply_xls_font(ws)
        self.omit_offset(ws, 5)
        self.color_omit_offset(ws, 5)

    def trend_reverse(self, ws) -> None:
        state = self.state
        ws.append([""])
        ws.append([state.draw_dates[state.start_serial] + state.serials[state.start_serial]])
        self.apply_xls_font(ws)
        for hit in detect_trend_reverse_hits(state, state.start_serial):
            ws.append(["博彩逆转：", "数字：%s" % hit.ball, "", hit.detail])
            self.apply_xls_font(ws)

    def pile(self, ws) -> None:
        for hit in detect_pile_hits(self.state, self.state.start_serial):
            ws.append(["层叠：", "数字：%02d" % hit.ball, "模式：%s" % hit.detail])
            self.apply_xls_font(ws)

    def re_pile(self, ws) -> None:
        for hit in detect_re_pile_hits(self.state, self.state.start_serial):
            ws.append(["反向层叠：", "数字：%02d" % hit.ball, "模式：%s" % hit.detail])
            self.apply_xls_font(ws)

    def n_bottom(self, ws) -> None:
        for hit in detect_n_bottom_hits(self.state, self.state.start_serial):
            prefix, detail = hit.detail.split("：", 1)
            ws.append([prefix + "：", "数字：%d" % hit.ball, "模式：%s" % detail])
            self.apply_xls_font(ws)

    def flag_range(self, ws) -> None:
        for hit in detect_flag_range_hits(self.state, self.state.start_serial):
            ws.append(["旗式排列：", "数字：%d" % hit.ball, "模式：%s" % hit.detail])
            self.apply_xls_font(ws)

    def add_info(self, ws) -> None:
        ws["B1"] = self.state.serials[0]

    def check_complete(self, ws) -> bool:
        state = self.state
        value = ws["B1"].value
        if value == state.serials[0]:
            print("no need to update.")
            raise SystemExit(0)
        if len(state.serials) > 1 and value == state.serials[1]:
            state.start_serial = 0
            print("update the newest.")
            return True

        for i in range(2, min(MAX_DRAWS, len(state.serials))):
            if value == state.serials[i]:
                state.start_serial = i - 1
                print("update from %s" % state.serials[state.start_serial])
                break
        return False

    def count_ball(self) -> None:
        self.file_odd_or_even(self.workbook["奇偶数表"])
        self.file_big_or_small(self.workbook["大小数表"])
        self.sum_offset(self.workbook["和值偏差表"])
        self.ball_range(self.workbook["区间表"])
        self.hot_or_cold(self.workbook["百分比表"])
        self.file_omit(self.workbook["遗漏表"])
        self.file_omit_offset(self.workbook["遗漏数字偏差表"])
        self.trend_reverse(self.workbook["中期表"])
        self.pile(self.workbook["中期表"])
        self.re_pile(self.workbook["中期表"])
        self.n_bottom(self.workbook["中期表"])
        self.flag_range(self.workbook["中期表"])
