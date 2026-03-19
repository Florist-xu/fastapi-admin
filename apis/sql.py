from fastapi import Request, APIRouter, FastAPI
from contextlib import asynccontextmanager
from utils.response import ResponseUtil
from tortoise import Tortoise
import traceback
import re


sqlAPI = APIRouter(prefix="/sql", tags=["sql链接"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行的操作
    yield
    # 关闭时执行的操作
    if db_state["connected"]:
        await Tortoise.close_connections()


# 当前数据库连接状态
db_state = {
    "connected": False,
    "config": {
        "host": "127.0.0.1",
        "port": 3306,
        "user": "root",
        "password": "",
        "database": "fastapi",
    }
}


@sqlAPI.post("/connect")
async def connect_db(request: Request):
    """动态连接数据库"""
    body = await request.json()
    host = body.get("host", "127.0.0.1")
    port = int(body.get("port", 3306))
    user = body.get("user", "root")
    password = body.get("password", "")
    database = body.get("database", "fastapi")

    if db_state["connected"]:
        try:
            await Tortoise.close_connections()
        except Exception:
            pass
        db_state["connected"] = False

    try:
        db_url = f"mysql://{user}:{password}@{host}:{port}/{database}"
        await Tortoise.init(db_url=db_url, modules={"models": []})

        conn = Tortoise.get_connection("default")
        await conn.execute_query("SELECT 1")

        db_state["connected"] = True
        db_state["config"] = {
            "host": host, "port": port,
            "user": user, "password": password,
            "database": database,
        }
        return ResponseUtil.success(data={"msg":f"已连接到 {database}@{host}:{port}"})
    except Exception as e:
        db_state["connected"] = False
        return ResponseUtil.error(msg="连接数据库失败" )


@sqlAPI.get("/status")
async def db_status():
    return ResponseUtil.success(msg="获取数据库状态成功", data={
         "connected": db_state["connected"],
         "config": {
            "host": db_state["config"]["host"],
            "port": db_state["config"]["port"],
            "user": db_state["config"]["user"],
            "database": db_state["config"]["database"]
        },
        "connected": db_state["connected"],
    })


@sqlAPI.post("/execute")
async def execute_model(request: Request):
    """接收模型代码，解析并建表"""
    if not db_state["connected"]:
        return ResponseUtil.error(msg="请先连接数据库")

    body = await request.json()
    code_str = body.get("code", "")

    if not code_str.strip():
        return ResponseUtil.error(msg="代码不能为空")

    try:
        tables = parse_model_code(code_str)
        if not tables:
            return ResponseUtil.error(msg="未检测到有效的模型类")

        conn = Tortoise.get_connection("default")
        created = []
        for table_name, sql in tables:
            await conn.execute_script(sql)
            created.append(table_name)
        
        return ResponseUtil.success(msg=f"成功创建 {len(created)} 张表", data={"tables": created})
    except Exception as e:
        return ResponseUtil.error(msg=f"执行失败,{str(e)}", data={"traceback": traceback.format_exc()})


@sqlAPI.get("/tables")
async def list_tables():
    if not db_state["connected"]:
        return ResponseUtil.error(msg="请先连接数据库")
    try:
        conn = Tortoise.get_connection("default")
        result = await conn.execute_query("SHOW TABLES")
        tables = [list(row.values())[0] for row in result[1]]
        return ResponseUtil.success(msg="刷新表成功", data={"tables": tables})
    except Exception as e:
        return ResponseUtil.error(msg=str(e))


@sqlAPI.get("/table/{table_name}")
async def table_detail(table_name: str):
    print(table_name,"表名称")
    if not db_state["connected"]:
        return ResponseUtil.error(msg="请先连接数据库")
    try:
        conn = Tortoise.get_connection("default")
        result = await conn.execute_query(f"SHOW FULL COLUMNS FROM `{table_name}`")
        # print(result)
        columns = []
        for row in result[1]:
            columns.append({
                "field": row.get("Field", ""),
                "type": row.get("Type", ""),
                "null": row.get("Null", ""),
                "key": row.get("Key", ""),
                "default": str(row.get("Default", "")),
                "extra": row.get("Extra", ""),
                "comment": row.get("Comment", ""),
            })
            in_data={
                "columns":columns,
                "table_name":table_name
            }
        return ResponseUtil.success(data=in_data)
    except Exception as e:
        return ResponseUtil.error(msg=str(e))


@sqlAPI.get("/reverse/{table_name}")
async def reverse_table(table_name: str):
    """从数据库表结构反推生成 Tortoise-ORM 模型代码（含外键关联）"""
    if not db_state["connected"]:
        return ResponseUtil.error(msg="请先连接数据库")
    try:
        conn = Tortoise.get_connection("default")
        # 1. 获取表字段详情
        result = await conn.execute_query(f"SHOW FULL COLUMNS FROM `{table_name}`")
        rows = result[1]
        
        # 2. 查询外键关联信息（关键新增）
        fk_result = await conn.execute_query("""
            SELECT 
                kcu.COLUMN_NAME,
                kcu.REFERENCED_TABLE_NAME,
                kcu.REFERENCED_COLUMN_NAME,
                rc.DELETE_RULE,
                rc.UPDATE_RULE
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
                ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
            WHERE kcu.TABLE_NAME = %s 
              AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
        """, [table_name])
        fk_rows = fk_result[1]
        # 构建外键映射：{字段名: 外键信息}
        fk_map = {row["COLUMN_NAME"]: row for row in fk_rows}

        class_name = table_name[0].upper() + table_name[1:]
        lines = [f"class {class_name}(Model):"]
        
        for row in rows:
            field = row.get("Field", "")
            col_type = row.get("Type", "").upper()
            null = row.get("Null", "NO") == "YES"
            key = row.get("Key", "")
            default = row.get("Default")
            comment = row.get("Comment", "")

            # --- 新增：判断是否为外键字段 ---
            if field in fk_map:
                fk_info = fk_map[field]
                ref_table = fk_info["REFERENCED_TABLE_NAME"]
                ref_col = fk_info["REFERENCED_COLUMN_NAME"]
                delete_rule = fk_info["DELETE_RULE"]
                update_rule = fk_info["UPDATE_RULE"]
                
                # 生成父表模型名（驼峰命名）
                ref_class = ref_table[0].upper() + ref_table[1:]
                # 构建 ForeignKeyField 参数
                parts = []
                parts.append(f'"models.{ref_class}"')  # 关联模型
                if ref_col != "id":
                    parts.append(f'to_field="{ref_col}"')  # 非默认id字段时指定
                if null:
                    parts.append("null=True")
                else:
                    parts.append("null=False")
                # 处理 on_delete / on_update
                if delete_rule:
                    parts.append(f'on_delete=fields.{delete_rule}')
                if update_rule:
                    parts.append(f'on_update=fields.{update_rule}')
                if comment:
                    parts.append(f'description="{comment}"')
                
                args_str = ", ".join(parts)
                lines.append(f"    {field} = fields.ForeignKeyField({args_str})")
                continue  # 外键字段跳过普通字段处理
            
            # --- 原有普通字段处理逻辑 ---
            field_type, extra_args = reverse_column_type(col_type)
            parts = []

            if key == "PRI":
                parts.append("pk=True")
            if field_type == "CharField" and "max_length" not in extra_args:
                extra_args["max_length"] = "255"
            for k, v in extra_args.items():
                parts.append(f"{k}={v}")
            parts.append(f"null={null}")
            if default is not None and key != "PRI":
                if field_type in ("CharField", "TextField"):
                    parts.append(f'default="{default}"')
                elif field_type == "BooleanField":
                    parts.append(f"default={'True' if default == '1' else 'False'}")
                else:
                    parts.append(f"default={default}")
            if comment:
                parts.append(f'description="{comment}"')

            args_str = ", ".join(parts)
            lines.append(f"    {field} = fields.{field_type}({args_str})")

        code = "\n".join(lines) + "\n"
        return ResponseUtil.success(data={"code": code, "table_name": table_name})
    except Exception as e:
        return ResponseUtil.error(msg=str(e))


def reverse_column_type(col_type: str):
    """将 MySQL 列类型映射回 Tortoise-ORM 字段类型"""
    col_type = col_type.upper().strip()
    extra = {}

    if col_type == "TINYINT(1)":
        return "BooleanField", extra
    if col_type.startswith("INT") or col_type == "TINYINT" or col_type.startswith("MEDIUMINT"):
        return "IntField", extra
    if col_type.startswith("BIGINT"):
        return "BigIntField", extra
    if col_type.startswith("SMALLINT"):
        return "SmallIntField", extra
    if col_type.startswith("VARCHAR"):
        m = re.search(r'\((\d+)\)', col_type)
        if m:
            extra["max_length"] = m.group(1)
        return "CharField", extra
    if col_type in ("TEXT", "LONGTEXT", "MEDIUMTEXT"):
        return "TextField", extra
    if col_type.startswith("DECIMAL"):
        m = re.search(r'\((\d+),(\d+)\)', col_type)
        if m:
            extra["max_digits"] = m.group(1)
            extra["decimal_places"] = m.group(2)
        return "DecimalField", extra
    if col_type in ("DOUBLE", "FLOAT"):
        return "FloatField", extra
    if col_type.startswith("DATETIME"):
        return "DatetimeField", extra
    if col_type == "DATE":
        return "DateField", extra
    if col_type == "JSON":
        return "JSONField", extra

    return "CharField", extra


@sqlAPI.delete("/table/{table_name}")
async def drop_table(table_name: str):
    if not db_state["connected"]:
        return ResponseUtil.error(msg="请先连接数据库")
    try:
        conn = Tortoise.get_connection("default")
        await conn.execute_script(f"DROP TABLE IF EXISTS `{table_name}`")
        return ResponseUtil.success(msg=f"表 {table_name} 已删除")
    except Exception as e:
        return ResponseUtil.error(msg=str(e))


@sqlAPI.post("/preview_sql")
async def preview_sql(request: Request):    
    body = await request.json()
    code_str = body.get("code", "")

    if not code_str.strip():
        return ResponseUtil.error(msg="请输入代码")

    try:
        tables = parse_model_code(code_str)
        if not tables:
            return ResponseUtil.error(msg="未解析到任何模型类")

        sql_text = "\n\n".join(sql for _, sql in tables)
        return ResponseUtil.success(msg="解析成功", data={"sql": sql_text})
    except Exception as e:
        return ResponseUtil.error(msg=str(e))


# ========== 纯文本解析，不依赖 exec ==========

def parse_model_code(code_str: str):
    """从 Python 模型代码文本中解析出所有模型类，生成建表SQL。
    返回 [(table_name, sql), ...]
    """
    results = []

    # 按 class 定义拆分
    class_pattern = re.compile(
        r'^class\s+(\w+)\s*\(\s*Model\s*\)\s*:', re.MULTILINE)
    matches = list(class_pattern.finditer(code_str))

    for i, match in enumerate(matches):
        class_name = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(code_str)
        body = code_str[start:end]

        # 解析字段行
        columns = []
        field_lines = re.findall(
            r'^    (\w+)\s*=\s*fields\.(\w+)\((.*)?\)\s*$', body, re.MULTILINE)

        for field_name, field_type, args_str in field_lines:
            col_sql = parse_field_to_sql(field_name, field_type, args_str)
            if col_sql:
                columns.append(col_sql)

        if not columns:
            columns.append("`id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY")

        table_name = class_name.lower()
        sql = f"CREATE TABLE IF NOT EXISTS `{table_name}` (\n"
        sql += ",\n".join(f"  {col}" for col in columns)
        sql += "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
        results.append((table_name, sql))

    return results


def parse_field_to_sql(field_name: str, field_type: str, args_str: str) -> str:
    """从字段文本解析生成SQL列定义"""
    args = parse_field_args(args_str)

    # 关系字段
    if field_type == "ForeignKeyField":
        col = f"`{field_name}_id` INT NULL"
        comment = args.get("description")
        if comment:
            col += f" COMMENT '{comment}'"
        return col
    if field_type == "ManyToManyField":
        return ""  # 多对多不生成列

    # 普通字段类型映射
    max_length = args.get("max_length", "255")
    max_digits = args.get("max_digits", "10")
    decimal_places = args.get("decimal_places", "2")

    type_map = {
        "IntField": "INT",
        "BigIntField": "BIGINT",
        "SmallIntField": "SMALLINT",
        "CharField": f"VARCHAR({max_length})",
        "TextField": "TEXT",
        "BooleanField": "TINYINT(1)",
        "DatetimeField": "DATETIME(6)",
        "DateField": "DATE",
        "DecimalField": f"DECIMAL({max_digits},{decimal_places})",
        "FloatField": "DOUBLE",
        "JSONField": "JSON",
    }

    sql_type = type_map.get(field_type, "VARCHAR(255)")
    pk = args.get("pk") == "True"
    nullable = args.get("null", "False") == "True"

    parts = [f"`{field_name}`", sql_type]

    if pk:
        parts.append("NOT NULL AUTO_INCREMENT PRIMARY KEY")
    else:
        parts.append("NULL" if nullable else "NOT NULL")
        # 默认值
        default = args.get("default")
        if default is not None:
            if field_type in ("CharField", "TextField"):
                # 去掉代码中的引号
                default = default.strip('"').strip("'")
                parts.append(f"DEFAULT '{default}'")
            elif field_type == "BooleanField":
                parts.append(f"DEFAULT {1 if default == 'True' else 0}")
            else:
                parts.append(f"DEFAULT {default}")

    # 描述 -> COMMENT
    description = args.get("description")
    if description:
        description = description.strip('"').strip("'")
        parts.append(f"COMMENT '{description}'")

    return " ".join(parts)


def parse_field_args(args_str: str) -> dict:
    """解析字段参数字符串，如 'pk=True, max_length=50, description="用户名"'
    返回 {'pk': 'True', 'max_length': '50', 'description': '用户名'}
    """
    result = {}
    if not args_str:
        return result

    # 用正则匹配 key=value 对，支持引号内含逗号
    pattern = re.compile(
        r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[^,]+)')
    for m in pattern.finditer(args_str):
        key = m.group(1).strip()
        value = m.group(2).strip().strip('"').strip("'")
        result[key] = value

    return result
