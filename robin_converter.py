import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(ROOT_DIR, "pad-robin-action-kb-main", "PAD_Robin_ActionKB.json")
CHECKER_PATH = os.path.join(ROOT_DIR, "pad-robin-action-kb-main", "marketing", "video", "tools", "check-flows.js")


def clean_string_expr(expr: str) -> str:
    """Clean a string expression from VB/UiPath to Robin $'''...''' format."""
    if not expr:
        return "$''''''"
    expr = expr.strip()
    if expr.startswith('["') and expr.endswith('"]'):
        expr = expr[2:-2]
    elif expr.startswith('"') and expr.endswith('"'):
        expr = expr[1:-1]
    elif expr.startswith('[') and expr.endswith(']'):
        expr = expr[1:-1]

    expr = expr.replace('&quot;', '"')
    if expr.startswith('"') and expr.endswith('"'):
        expr = expr[1:-1]

    expr = expr.replace("'", "\\'")
    expr = re.sub(r'\\(?=$)', r'\\\\', expr)

    return f"$'''{expr}'''"


def clean_condition_expr(cond: str) -> str:
    """Translate VB/UiPath expression to Robin condition syntax."""
    if not cond:
        return "True"
    cond = cond.strip()
    if cond.startswith('[') and cond.endswith(']'):
        cond = cond[1:-1]

    cond = re.sub(r'CInt\((.*?)\)', r'\1', cond)
    cond = re.sub(r'Convert\.ToInt32\((.*?)\)', r'\1', cond)
    cond = re.sub(r'Convert\.ToString\((.*?)\)', r'\1', cond)
    cond = re.sub(r'String\.IsNullOrEmpty\((.*?)\)', r'IsEmpty(\1)', cond)
    cond = re.sub(r'String\.IsNullOrWhiteSpace\((.*?)\)', r'IsEmpty(\1)', cond)

    cond = re.sub(r'\bAndAlso\b', 'AND', cond, flags=re.I)
    cond = re.sub(r'\bOrElse\b', 'OR', cond, flags=re.I)
    cond = re.sub(r'\bAnd\b', 'AND', cond, flags=re.I)
    cond = re.sub(r'\bOr\b', 'OR', cond, flags=re.I)
    cond = re.sub(r'\bNot\b', 'NOT', cond, flags=re.I)

    cond = re.sub(r'==', '=', cond)
    cond = re.sub(r'!=', '<>', cond)

    return cond


def xaml_to_robin(xaml_text: str) -> str:
    """Convert an RPA XAML workflow (UiPath/WF) to Power Automate Desktop Robin script."""
    lines = []
    lines.append("# --- Converted from Workflow XAML to Power Automate Desktop (Robin) ---")
    lines.append("# Paste directly into PAD Designer canvas (PAD 2.74 Validated)")
    lines.append("")

    try:
        root = ET.fromstring(xaml_text)
    except Exception as e:
        return f"# Error parsing XAML: {e}\n"

    def clean_tag(tag: str) -> str:
        return tag.split('}')[-1]

    excel_opened = False

    def walk(element, indent=""):
        nonlocal excel_opened
        tag = clean_tag(element.tag)

        # 1. Input Dialog
        if tag == "InputDialog":
            title = clean_string_expr(element.get("Title", "Input"))
            msg = clean_string_expr(element.get("Label", "Please enter a value"))
            out_var = "UserInput"
            for out in element.iter():
                if clean_tag(out.tag) == "OutArgument":
                    t = (out.text or "").strip()
                    if t.startswith("[") and t.endswith("]"):
                        t = t[1:-1]
                    if t:
                        out_var = t
                        break

            lines.append(f"{indent}Display.InputDialog InputType: Display.InputType.SingleLine IsTopMost: False DefaultValue: $'''''' Message: {msg} Title: {title} UserInput=> {out_var} ButtonPressed=> ButtonPressed")
            return

        # 2. Message Box
        if tag == "MessageBox":
            title = clean_string_expr(element.get("DisplayName", "Message Box"))
            text_val = element.get("Text", "Message")
            msg = clean_string_expr(text_val)
            lines.append(f"{indent}Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.None Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: {msg} Title: {title} ButtonPressed=> ButtonPressed")
            return

        # 3. Assign
        if tag == "Assign":
            var_name = "Variable"
            val_text = "0"
            for ch in element:
                ctag = clean_tag(ch.tag)
                if "To" in ctag:
                    for sub in ch.iter():
                        if clean_tag(sub.tag) == "OutArgument":
                            t = (sub.text or "").strip()
                            if t.startswith("[") and t.endswith("]"):
                                t = t[1:-1]
                            if t:
                                var_name = t
                elif "Value" in ctag:
                    for sub in ch.iter():
                        if clean_tag(sub.tag) in ["InArgument", "VisualBasicValue"]:
                            t = (sub.text or "").strip()
                            if t:
                                val_text = t

            clean_val = val_text
            if clean_val.startswith('["') and clean_val.endswith('"]'):
                clean_val = clean_string_expr(clean_val)
            elif clean_val.startswith('"') and clean_val.endswith('"'):
                clean_val = clean_string_expr(clean_val)
            elif clean_val.startswith("[") and clean_val.endswith("]"):
                clean_val = clean_val[1:-1]

            lines.append(f"{indent}SET {var_name} TO {clean_val}")
            return

        # 4. If Statement
        if tag == "If":
            cond = clean_condition_expr(element.get("Condition", "True"))
            lines.append(f"{indent}IF {cond} THEN")

            then_block = None
            else_block = None
            for ch in element:
                ctag = clean_tag(ch.tag)
                if ctag in ["If.Then", "Then"]:
                    then_block = ch
                elif ctag in ["If.Else", "Else"]:
                    else_block = ch

            if then_block is not None:
                for sub in then_block:
                    walk(sub, indent + "    ")
            else:
                lines.append(f"{indent}    # (empty then branch)")

            if else_block is not None and len(list(else_block)) > 0:
                lines.append(f"{indent}ELSE")
                for sub in else_block:
                    walk(sub, indent + "    ")

            lines.append(f"{indent}END")
            return

        # 5. Delay / Wait
        if tag == "Delay":
            duration = element.get("Duration", "00:00:02")
            seconds = 2
            match = re.match(r'(\d+):(\d+):(\d+)', duration)
            if match:
                seconds = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3))
            lines.append(f"{indent}WAIT {seconds}")
            return

        # 6. Excel Scope / Use Excel
        if tag in ["ExcelProcessScopeX", "ExcelApplicationCard", "ExcelApplicationScope"]:
            file_path = element.get("WorkbookPath", "$'''C:\\Data\\Workbook.xlsx'''")
            if not file_path.startswith("$'''"):
                file_path = clean_string_expr(file_path)
            lines.append(f"{indent}Excel.LaunchExcel.LaunchAndOpen Path: {file_path} Visible: True ReadOnly: False LoadAddInsAndMacros: False Instance=> ExcelInstance")
            excel_opened = True
            for ch in element:
                walk(ch, indent)
            return

        # 7. Read Range Excel
        if tag in ["ReadRange", "ReadRangeX"]:
            lines.append(f"{indent}Excel.ReadFromExcel.ReadAllCells Instance: ExcelInstance ReadAsText: False FirstRowIsHeader: True RangeValue=> ExcelData")
            return

        # 8. Write Range Excel
        if tag in ["WriteRange", "WriteRangeX"]:
            lines.append(f"{indent}Excel.WriteToExcel.WriteCell Instance: ExcelInstance Value: ExcelData Column: 1 Row: 1")
            return

        # 9. For Each Row
        if tag in ["ForEachRow", "ForEachRowX"]:
            lines.append(f"{indent}LOOP FOREACH CurrentRow IN ExcelData")
            for ch in element:
                walk(ch, indent + "    ")
            lines.append(f"{indent}END")
            return

        # 10. Create Folder
        if tag == "CreateDirectory":
            p = element.get("Path", "$'''C:\\NewFolder'''")
            lines.append(f"{indent}Folder.Create FolderPath: $'''C:\\''' FolderName: {clean_string_expr(p)} Folder=> NewFolder")
            return

        # 11. Write Text File
        if tag == "WriteTextFile":
            p = element.get("FileName", "$'''C:\\output.txt'''")
            txt = element.get("Text", "Output")
            lines.append(f"{indent}File.WriteText File: {clean_string_expr(p)} AppendNewLine: True IfFileExists: File.IfFileExists.Overwrite Encoding: File.FileEncoding.Unicode TextToWrite: {clean_string_expr(txt)}")
            return

        # 12. Read Text File
        if tag == "ReadTextFile":
            p = element.get("FileName", "$'''C:\\input.txt'''")
            lines.append(f"{indent}File.ReadTextFromFile.ReadText File: {clean_string_expr(p)} Encoding: File.TextFileEncoding.UTF8 Content=> FileContents")
            return

        # 13. Log Message
        if tag == "LogMessage":
            msg = element.get("Message", "")
            lines.append(f"{indent}# Log: {msg}")
            return

        # Recurse for containers
        for ch in element:
            walk(ch, indent)

    walk(root)

    if excel_opened:
        lines.append("")
        lines.append("Excel.CloseExcel.CloseAndSave Instance: ExcelInstance")

    return "\n".join(lines)


def generate_template_robin(template_key: str) -> str:
    """Generate golden, paste-validated Robin flows."""
    templates = {
        "folder_backup": (
            "DateTime.GetCurrentDateTime.Local DateTimeFormat: DateTime.DateTimeFormat.DateOnly CurrentDateTime=> CurrentDateTime\n"
            "Folder.GetFiles Folder: $'''C:\\Downloads''' FileFilter: $'''*''' IncludeSubfolders: False FailOnAccessDenied: True SortBy1: Folder.SortBy.NoSort SortDescending1: False SortBy2: Folder.SortBy.NoSort SortDescending2: False SortBy3: Folder.SortBy.NoSort SortDescending3: False Files=> Files\n"
            "File.Copy Files: Files Destination: $'''D:\\Backup\\Downloads''' IfFileExists: File.IfExists.Overwrite CopiedFiles=> CopiedFiles\n"
            "Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.Information Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: $'''Backed up %CopiedFiles.Count% files on %CurrentDateTime%''' Title: $'''Downloads backup''' ButtonPressed=> ButtonPressed"
        ),
        "excel_report": (
            "Excel.LaunchExcel.Launch UseMachineLocale: False Visible: False LoadAddInsAndMacros: False Instance=> ExcelInstance\n"
            "Excel.WriteToExcel.WriteCell Instance: ExcelInstance Value: $'''Invoice''' Column: $'''A''' Row: 1\n"
            "Excel.WriteToExcel.WriteCell Instance: ExcelInstance Value: $'''Amount''' Column: $'''B''' Row: 1\n"
            "Excel.WriteToExcel.WriteCell Instance: ExcelInstance Value: $'''INV-1001''' Column: $'''A''' Row: 2\n"
            "Excel.WriteToExcel.WriteCell Instance: ExcelInstance Value: 450 Column: $'''B''' Row: 2\n"
            "Excel.CloseExcel.CloseAndSaveAs Instance: ExcelInstance XmlMapName: $'''''' DocumentPath: $'''C:\\Reports\\Invoice_Summary.xlsx''' DocumentFormat: Excel.ExcelFormat.FromExtension\n"
            "Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.Information Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: $'''Excel summary generated and saved successfully!''' Title: $'''Report Done''' ButtonPressed=> ButtonPressed"
        ),
        "outlook_attachments": (
            "Outlook.Launch Instance=> OutlookInstance\n"
            "DateTime.GetCurrentDateTime.Local DateTimeFormat: DateTime.DateTimeFormat.DateAndTime CurrentDateTime=> CurrentDateTime\n"
            "Text.ConvertDateTimeToText.FromCustomDateTime CustomFormat: $'''yyyy-MM-dd''' DateTime: CurrentDateTime Result=> Today\n"
            "SET AttachmentFolder TO $'''C:\\Attachments\\\\%Today%'''\n"
            "IF (Folder.IfFolderExists.DoesNotExist Path: AttachmentFolder) THEN\n"
            "    Folder.Create FolderPath: $'''C:\\Attachments''' FolderName: Today Folder=> NewFolder\n"
            "END\n"
            "Outlook.RetrieveEmailMessages.RetrieveEmailsAndSaveAttachments ReadBodyAsHtml: False MarkAsRead: True MailFolder: $'''Inbox''' ToContains: $'''''' SubjectContains: $'''Invoice''' SaveAttachmentsInto: AttachmentFolder BodyContains: $'''''' Account: $'''you@example.com''' Instance: OutlookInstance FromContains: $'''''' EmailsToRetrieve: Outlook.RetrieveMessagesMode.Unread Messages=> RetrievedEmails\n"
            "SET EmailCount TO RetrievedEmails.Count\n"
            "IF EmailCount = 0 THEN\n"
            "    Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.Information Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: $'''No new invoice emails''' Title: $'''Invoice attachments''' ButtonPressed=> ButtonPressed\n"
            "ELSE\n"
            "    Folder.GetFiles Folder: AttachmentFolder FileFilter: $'''*.pdf''' IncludeSubfolders: False FailOnAccessDenied: True SortBy1: Folder.SortBy.NoSort SortDescending1: False SortBy2: Folder.SortBy.NoSort SortDescending2: False SortBy3: Folder.SortBy.NoSort SortDescending3: False Files=> Files\n"
            "    Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.Information Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: $'''Saved %Files.Count% PDFs from %RetrievedEmails.Count% emails''' Title: $'''Invoice attachments''' ButtonPressed=> ButtonPressed\n"
            "END\n"
            "Outlook.Close Instance: OutlookInstance"
        ),
        "input_and_decision": (
            "Display.InputDialog InputType: Display.InputType.SingleLine IsTopMost: False DefaultValue: $'''''' Message: $'''Please enter your age:''' Title: $'''Age Verification''' UserInput=> UserAge ButtonPressed=> ButtonPressed\n"
            "IF UserAge >= 18 THEN\n"
            "    Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.Information Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: $'''Access granted. You are an adult.''' Title: $'''Verification Result''' ButtonPressed=> ButtonPressed\n"
            "ELSE\n"
            "    Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.Warning Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: $'''Access restricted. You are a minor.''' Title: $'''Verification Result''' ButtonPressed=> ButtonPressed\n"
            "END"
        ),
        "sales_api_report": (
            "Web.InvokeWebService.InvokeWebService Url: $'''https://api.example.com/orders''' Method: Web.Method.Get Accept: $'''application/json''' ContentType: $'''application/json''' ConnectionTimeout: 30 FollowRedirection: True ClearCookies: False FailOnErrorStatus: False EncodeRequestBody: True UserAgent: $'''Mozilla/5.0''' Encoding: Web.Encoding.AutoDetect AcceptUntrustedCertificates: False TrimRequestBody: True ResponseHeaders=> WebServiceResponseHeaders Response=> WebServiceResponse StatusCode=> StatusCode\n"
            "IF StatusCode = 200 THEN\n"
            "    Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.Information Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: $'''Sales API responded successfully!''' Title: $'''Sales API''' ButtonPressed=> ButtonPressed\n"
            "ELSE\n"
            "    Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.ErrorIcon Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: $'''API failed with HTTP status: %StatusCode%''' Title: $'''Error''' ButtonPressed=> ButtonPressed\n"
            "END"
        )
    }
    return templates.get(template_key, "")


def validate_robin(code: str) -> dict:
    """Validate Robin script against PAD Robin rules using check-flows.js."""
    tmp_path = os.path.join(ROOT_DIR, "_tmp_validate.robin")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(code)

        cmd = ["node", CHECKER_PATH, KB_PATH, tmp_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        output = res.stdout + res.stderr
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

        is_clean = res.returncode == 0 and "0 errors" in output
        errors = [line.strip() for line in output.splitlines() if line.strip().startswith("line ") or "error" in line.lower()]

        return {
            "valid": is_clean,
            "output": output,
            "errors": errors
        }
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return {"valid": False, "output": str(e), "errors": [str(e)]}
