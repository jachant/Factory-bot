import calendar
import os
from datetime import datetime

import xlsxwriter
from xlsxwriter.utility import xl_col_to_name

from app.config.genexcel import (
    ACTIVITIES,
    CORRECTIONS,
    FILENAME_TEMPLATE,
    MONTH_HEADER,
    REPORT,
    CorrectionFields,
    ReportColumn,
    Styles,
    Table,
    activity_table,
    corrections_table,
    report_table,
)
from app.db.exceptions import BadKeyError
from app.db.models import Activity, User, WorkerPositionActual, WorkerProfile
from app.db.requests import (
    get_factory,
    get_profile,
    get_report_activities,
    get_report_corrections,
    get_report_user_activities,
    get_report_users,
    get_shifts_count,
)
from app.utils import setup_logger
from app.utils.month import MONTHS
from app.utils.uploader import get_disk_link

logger = setup_logger(__name__)


class GeneratorExcel:
    def __init__(self, factory_id: int, year: int, month: int):
        self.year = year
        self.month = month
        self.factory_id = factory_id
        self.styles = {}

    async def free(self):
        logger.info(f"Очистка {self.filename}")
        if os.path.exists(self.filename):
            os.remove(self.filename)
            logger.info(f"{self.filename} успешно удалён")

    async def generate(self) -> str:
        logger.info("Генерация excel файла")
        self.factory = await get_factory(self.factory_id)

        self.filename = FILENAME_TEMPLATE.format(
            self.factory.factory_name,
            MONTHS.get(self.month).lower(),
            self.year,
            datetime.now().strftime("%d-%m-%Y"),
        )
        self.wb = xlsxwriter.Workbook(self.filename)
        logger.debug("Загрузка стилей")
        for style in Styles:
            self.styles[style] = self.wb.add_format(style.value)

        await self.add_activities_sheet()
        await self.add_corrections_sheet()
        await self.add_report_sheet()
        self.wb.close()
        return self.filename

    async def add_activities_sheet(self):
        logger.debug("Создание листа с activities")
        activities = await get_report_activities(self.factory_id, self.year, self.month)
        # Add global code styles
        for activity in activities:
            self.styles[activity.id] = self.wb.add_format(
                {"bg_color": "#" + activity.color} | Styles.BASIC_CENTER.value
            )

        ws = self.wb.add_worksheet(ACTIVITIES)
        # Add headers
        for col, header in enumerate(activity_table[Table.DESC].keys()):
            ws.write(0, col, header, self.styles.get(Styles.HEADER))
        # Add body code
        for row, activity in enumerate(activities, start=1):
            for col, attr in enumerate(activity_table[Table.DESC].values()):
                # Styles
                style = self.styles.get(attr[Table.Desc.STYLE])
                if attr[Table.Desc.MAP] == Activity.code:
                    style = self.styles.get(activity.id)
                # ---
                ws.write(row, col, getattr(activity, attr[Table.Desc.MAP].key), style)
        # Add column widths
        for col, width in activity_table[Table.COLUMN].items():
            ws.set_column(col, width)

    async def add_corrections_sheet(self):
        logger.debug("Создание листа с corrections")
        corrections = await get_report_corrections(self.factory_id, self.year, self.month)
        ws = self.wb.add_worksheet(CORRECTIONS)

        # Add headers
        for col, header in enumerate(corrections_table[Table.DESC].keys()):
            ws.write(0, col, header, self.styles.get(Styles.HEADER))
        # Add body code
        for row, correction in enumerate(corrections, start=1):
            for col, attr in enumerate(corrections_table[Table.DESC].values()):
                # Styles
                style = self.styles.get(attr[Table.Desc.STYLE])
                if attr[Table.Desc.MAP] == CorrectionFields.INIT_CODE:
                    style = self.styles.get(correction.get(CorrectionFields.INIT_CODE_ID))
                elif attr[Table.Desc.MAP] == CorrectionFields.NEW_CODE:
                    style = self.styles.get(correction.get(CorrectionFields.NEW_CODE_ID))

                # ---
                ws.write(row, col, getattr(correction, attr[Table.Desc.MAP]), style)
        # Add column widths
        for col, width in corrections_table[Table.COLUMN].items():
            ws.set_column(col, width)

    async def add_report_sheet(self):
        logger.debug("Создание листа с report")
        ws = self.wb.add_worksheet(REPORT)

        days_num = calendar.monthrange(self.year, self.month)[1]
        # Add headers
        before_days = True
        start_merge_month = 0
        end_fill_table = 0
        shifts = await get_shifts_count(self.factory_id, self.year, self.month)
        offsets = [0] * (days_num + 1)
        for i in range(1, days_num + 1):
            offsets[i] = offsets[i - 1] + shifts.get(i - 1, 1) - 1
        for col, header in enumerate(report_table[Table.DESC].keys()):
            if header != ReportColumn.DAYS:
                col_i = col if before_days else days_num + col - 1 + offsets[i + 1]
                end_fill_table = col_i
                ws.merge_range(
                    2,
                    col_i,
                    3,
                    col_i,
                    header,
                    self.styles.get(Styles.HEADER_REPORT if before_days else Styles.HEADER_90),
                )
            else:
                before_days = False
                start_merge_month = col
                for i in range(days_num):
                    count = shifts.get(i + 1, 1)
                    col_i = col + i + offsets[i + 1]
                    if count != 1:
                        ws.merge_range(
                            3,
                            col_i,
                            3,
                            col_i + count - 1,
                            i + 1,
                            self.styles.get(Styles.HEADER_REPORT),
                        )
                    else:
                        ws.write(
                            3,
                            col_i,
                            i + 1,
                            self.styles.get(Styles.HEADER_REPORT),
                        )
        days_num += offsets[-1]
        ws.merge_range(
            2,
            start_merge_month,
            2,
            start_merge_month + days_num - 1,
            MONTH_HEADER[0].format(MONTHS[self.month], self.year),
            self.styles.get(MONTH_HEADER[1]),
        )
        ws.merge_range(
            0, 0, 0, end_fill_table, self.factory.company_name, self.styles.get(Styles.TITLE)
        )
        ws.merge_range(
            1, 0, 1, end_fill_table, self.factory.factory_name, self.styles.get(Styles.TITLE)
        )

        users_res = await get_report_users(self.factory_id, self.year, self.month)
        START_WITH = 4
        row = 0
        col = 0
        last_row = len(users_res) + START_WITH + 1
        for row, (user, is_master) in enumerate(users_res, start=START_WITH):
            user: User
            for col, attr in enumerate(report_table[Table.DESC].values()):
                obj_key = attr[Table.Desc.MAP]
                style = self.styles.get(attr[Table.Desc.STYLE])
                match obj_key:
                    case ReportColumn.NUM:
                        ws.write(row, col, row - START_WITH + 1, style)
                    case User.fullname:
                        ws.write(row, col, getattr(user, obj_key.key), style)
                    case WorkerProfile.job:
                        if is_master:
                            style = self.styles.get(Styles.MASTER)
                        try:
                            profile = await get_profile(user.id, self.year, self.month)
                        except BadKeyError as e:
                            logger.debug(e)
                            profile = await get_profile(user.id)
                        ws.write(row, col, getattr(profile, obj_key.key), style)
                    case WorkerPositionActual.activity_id:
                        activities = await get_report_user_activities(
                            self.factory_id, user.id, self.year, self.month
                        )
                        # Set boarders
                        for day in range(1, days_num + 1):
                            ws.write_blank(
                                row, col + day - 1, None, self.styles.get(Styles.BORDERS)
                            )
                        day = 0
                        offset_local = 0
                        col_i = 0
                        for activity, act_date, link in activities:
                            activity: Activity
                            act_date: datetime
                            style = self.styles.get(activity.id)
                            if day != act_date.day:
                                day = act_date.day
                                offset_local = 0
                                col_i = col + day + offsets[day] - 1
                            else:
                                offset_local += 1
                                col_i = col + day + offsets[day] - 1 + offset_local
                            ws.write_number(row, col_i, activity.duration, style)
                            ws.write_url(
                                last_row,
                                col_i,
                                link,
                                string="Фото наряда",
                                cell_format=self.styles.get(Styles.LINK_90),
                            )

                    case ReportColumn.SHIFT:
                        ws.write_formula(
                            row,
                            col + days_num - 1,
                            f"=COUNT(D{row+1}:{xl_col_to_name(days_num + col - 2)}{row+1})",
                            style,
                        )
                    case ReportColumn.HOURS:
                        ws.write_formula(
                            row,
                            col + days_num - 1,
                            f"=SUM(D{row+1}:{xl_col_to_name(days_num + col - 3)}{row+1})",
                            style,
                        )
                    case WorkerProfile.rate:
                        try:
                            profile = await get_profile(user.id, self.year, self.month)
                        except BadKeyError as e:
                            logger.debug(e)
                            profile = await get_profile(user.id)
                        ws.write_number(
                            row, col + days_num - 1, getattr(profile, obj_key.key), style
                        )
                    case ReportColumn.SALARY:
                        ws.write_formula(
                            row,
                            col + days_num - 1,
                            f"={xl_col_to_name(days_num + col - 3)}{row+1}*\
                                {xl_col_to_name(days_num + col - 2)}{row+1}",
                            style,
                        )
        row += 1
        col += days_num - 1
        ws.write_formula(
            row,
            col,
            f"=SUM({xl_col_to_name(col)}5:{xl_col_to_name(col)}{row})",
            self.styles.get(Styles.TOTAL),
        )
        ws.merge_range(last_row, 0, last_row, 2, None)
        ws.write_url(
            last_row,
            0,
            await get_disk_link(),
            string="Ссылка на диск",
            cell_format=self.styles.get(Styles.LINK),
        )
        # Add column widths
        before_columns = -1
        for col, width in report_table[Table.COLUMN].items():
            if isinstance(col, ReportColumn):
                if col == ReportColumn.DAYS:
                    for i in range(1, days_num + 1):
                        col_i = before_columns + i
                        ws.set_column(col_i, col_i, width)
                else:
                    col_i = before_columns + col + days_num
                    ws.set_column(col_i, col_i, width)
            else:
                before_columns += 1
                ws.set_column(col, width)
        # Add row heights
        for row, height in report_table[Table.ROW].items():
            ws.set_row(row, height)
