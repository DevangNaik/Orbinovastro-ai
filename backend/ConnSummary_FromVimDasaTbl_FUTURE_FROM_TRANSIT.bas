
Option Explicit

'=========================================================
' Batch output of ConnSummary for future MD?DEHA windows
'
' INPUT (Power Query output table):
'   VimDasaTbl
' Expected columns (aliases supported):
'   MD, AD, PD, SU, PRANA, DEH
'   WindowStart (or DasaDate) and WindowEnd (or NextDasaDate)
'   Optional: DBASPD, row no.
'
' OUTPUT:
'   Creates/clears a separate sheet and writes a flat table:
'     TransitDate, WindowStart, WindowEnd, DBASPD, Seq_MD..Seq_DEH
'     + all columns returned by AnalyzeStackConnectivity()
'
' Notes:
' - Uses GenerateStackFromPlTbl + AnalyzeStackConnectivity
' - Designed for speed: turns off screen updates, writes in blocks
'=========================================================

'======================
' Button-friendly runners (no arguments)
'======================
Public Sub Run_OutputfutureEvents_1000()
    'Runs first 1000 sequence windows from VimDasaTbl
    Output_FutureConnSummary_ToSheet "FutureConnSummary_Output", False, 1000
End Sub

Public Sub Run_OutputfutureEvents_All()
    'Runs ALL sequence windows from VimDasaTbl
    Output_FutureConnSummary_ToSheet "FutureConnSummary_Output", False, 0
End Sub

Public Sub Output_FutureConnSummary_ToSheet(Optional ByVal outSheetName As String = "FutureConnSummary_Output", _
                                           Optional ByVal includeCurrentWindow As Boolean = False, _
                                           Optional ByVal maxSeqRows As Long = 1000)
    On Error GoTo fail

    ' Ensure caches are loaded (PlTbl + VimDasa cache)
    LoadCaches

    Dim lo As ListObject
    Set lo = FindTableAcrossWorkbook("VimDasaTbl")
    If lo Is Nothing Then
        MsgBox "Table not found: VimDasaTbl", vbExclamation
        Exit Sub
    End If
    If lo.DataBodyRange Is Nothing Then
        MsgBox "Table VimDasaTbl has no rows.", vbExclamation
        Exit Sub
    End If

    Dim hdr As Object
    Set hdr = MapHeaders(lo.HeaderRowRange)

    Dim cMD As Long, cAD As Long, cPD As Long, cSU As Long, cPR As Long, cDEH As Long
    Dim cDD As Long, cDB As Long, cRowNo As Long

    cMD = HCol(hdr, Array("MD", "DASA", "MAHADASHA"))
    cAD = HCol(hdr, Array("AD", "BHUKTI", "ANTARDASHA"))
    cPD = HCol(hdr, Array("PD", "PRATYANTAR", "PRATYANTARDASHA"))
    cSU = HCol(hdr, Array("SU", "SUKSHMA"))
    cPR = HCol(hdr, Array("PRANA", "PRA", "PRAN"))
    cDEH = HCol(hdr, Array("DEH", "DEHA"))

    'VimDasaTbl provides DasaDate; we compute winEnd from the next row's DasaDate.
    cDD = HCol(hdr, Array("DASADATE", "DASA DATE", "DATE"))

    cDB = HCol(hdr, Array("DBASPD", "SEQKEY", "KEY"))
    cRowNo = HCol(hdr, Array("ROW NO.", "ROWNO", "ROW", "IDX", "INDEX"))

    If cMD = 0 Or cAD = 0 Or cPD = 0 Or cSU = 0 Or cPR = 0 Or cDEH = 0 Then
        MsgBox "Missing required MD..DEH columns in VimDasaTbl.", vbExclamation
        Exit Sub
    End If
    If cDD = 0 Then
        MsgBox "Missing DasaDate column in VimDasaTbl.", vbExclamation
        Exit Sub
    End If

Dim transitDate As Date
    transitDate = GetTransitDateSafe()

    ' Prepare output sheet
    Dim wsOut As Worksheet
    Set wsOut = GetOrCreateSheet(outSheetName)
    wsOut.Cells.Clear

    ' Build header from AnalyzeStackConnectivity header + our extra columns
    Dim planets6(1 To 6) As String
    planets6(1) = "Su": planets6(2) = "Mo": planets6(3) = "Ma"
    planets6(4) = "Me": planets6(5) = "Ju": planets6(6) = "Ve"

    ' Use a dummy call to get the analysis header (safe)
    Dim dummyStack As Variant, dummyAnaly As Variant
    Dim dummy6(1 To 6) As String
    dummy6(1) = "Su": dummy6(2) = "Mo": dummy6(3) = "Ma"
    dummy6(4) = "Me": dummy6(5) = "Ju": dummy6(6) = "Ve"
    dummyStack = GenerateStackFromPlTbl(dummy6)
    dummyAnaly = AnalyzeStackConnectivity(dummyStack, dummy6)

    Dim extraHeaders As Variant
    extraHeaders = Array("TransitDate", "WindowStart", "WindowEnd", "DBASPD", "Seq_MD", "Seq_AD", "Seq_PD", "Seq_SU", "Seq_PRANA", "Seq_DEH", "Seq_RowNo")

    Dim analyCols As Long
    analyCols = UBound(dummyAnaly, 2) - LBound(dummyAnaly, 2) + 1

    Dim totalCols As Long
    totalCols = (UBound(extraHeaders) - LBound(extraHeaders) + 1) + analyCols

    Dim headerArr() As Variant
    ReDim headerArr(1 To 1, 1 To totalCols)

    Dim i As Long, j As Long, baseCol As Long
    baseCol = 1
    For i = LBound(extraHeaders) To UBound(extraHeaders)
        headerArr(1, baseCol) = extraHeaders(i)
        baseCol = baseCol + 1
    Next i

    For j = 0 To analyCols - 1
        headerArr(1, baseCol + j) = dummyAnaly(LBound(dummyAnaly, 1), LBound(dummyAnaly, 2) + j)
    Next j

    wsOut.Range("A1").Resize(1, totalCols).Value = headerArr
    wsOut.rows(1).Font.Bold = True

    ' Turn off Excel overhead
    Dim calcMode As XlCalculation
    calcMode = Application.Calculation
    Application.ScreenUpdating = False
    Application.EnableEvents = False
    Application.Calculation = xlCalculationManual

    Dim data As Variant
    data = lo.DataBodyRange.value2

    Dim processedSeqRows As Long
    processedSeqRows = 0


    Dim r As Long
    Dim outRow As Long
    outRow = 2

    If UBound(data, 1) < 2 Then
        MsgBox "VimDasaTbl has fewer than 2 rows; cannot compute WindowEnd from next row.", vbExclamation
        GoTo cleanExit
    End If

    For r = 1 To UBound(data, 1) - 1

        Dim md As String, ad As String, pd As String, su As String, prana As String, deh As String
        md = Trim$(CStr(data(r, cMD)))
        ad = Trim$(CStr(data(r, cAD)))
        pd = Trim$(CStr(data(r, cPD)))
        su = Trim$(CStr(data(r, cSU)))
        prana = Trim$(CStr(data(r, cPR)))
        deh = Trim$(CStr(data(r, cDEH)))

        Dim wStart As Variant, winEnd As Variant
        wStart = data(r, cDD)
        winEnd = data(r + 1, cDD)

        If includeCurrentWindow = False Then
            ' Future-only: WindowStart >= TransitDate
            If IsDate(wStart) Then
                If CDate(wStart) < transitDate Then GoTo NextR
            End If
        Else
            ' Current onward: WindowEnd > TransitDate
            If IsDate(winEnd) Then
                If CDate(winEnd) <= transitDate Then GoTo NextR
            End If
        End If

        Dim dbaspd As String
        If cDB > 0 Then
            dbaspd = Trim$(CStr(data(r, cDB)))
        Else
            dbaspd = md & ad & pd & su & prana & deh
        End If

        Dim rowNo As Variant
        If cRowNo > 0 Then rowNo = data(r, cRowNo) Else rowNo = r

        Dim seq6(1 To 6) As String
        seq6(1) = md: seq6(2) = ad: seq6(3) = pd
        seq6(4) = su: seq6(5) = prana: seq6(6) = deh

        Dim stack As Variant, analy As Variant
        stack = GenerateStackFromPlTbl(seq6)
        If Not IsArray(stack) Then GoTo NextR

        analy = AnalyzeStackConnectivity(stack, seq6)
        If Not IsArray(analy) Then GoTo NextR

        ' analy includes header at row 0; copy only data rows (row >=1)
        Dim analyRows As Long
        analyRows = UBound(analy, 1) - LBound(analy, 1)

        If analyRows <= 0 Then GoTo NextR

        Dim block() As Variant
        ReDim block(1 To analyRows, 1 To totalCols)

        Dim rr As Long, cc As Long
        For rr = 1 To analyRows
            ' Extra columns
            block(rr, 1) = transitDate
            block(rr, 2) = wStart
            block(rr, 3) = winEnd
            block(rr, 4) = dbaspd
            block(rr, 5) = md
            block(rr, 6) = ad
            block(rr, 7) = pd
            block(rr, 8) = su
            block(rr, 9) = prana
            block(rr, 10) = deh
            block(rr, 11) = rowNo

            ' Analysis columns
            For cc = 1 To analyCols
                block(rr, 11 + cc) = analy(LBound(analy, 1) + rr, LBound(analy, 2) + (cc - 1))
            Next cc
        Next rr

        wsOut.Range("A" & outRow).Resize(analyRows, totalCols).Value = block
        outRow = outRow + analyRows

        processedSeqRows = processedSeqRows + 1
        If maxSeqRows > 0 And processedSeqRows >= maxSeqRows Then Exit For


NextR:
    Next r


    ' Create/refresh output table on the output sheet (so it exists even if the sheet was new)
    Dim outLastRow As Long, outLastCol As Long
    outLastRow = outRow - 1
    outLastCol = totalCols

    If outLastRow >= 1 Then
        Dim loOut As ListObject
        On Error Resume Next
        Set loOut = wsOut.ListObjects("tbl_OutputFutureEvents")
        On Error GoTo 0

        If Not loOut Is Nothing Then
            loOut.Unlist
        End If

        Dim outRng As Range
        Set outRng = wsOut.Range(wsOut.Cells(1, 1), wsOut.Cells(outLastRow, outLastCol))

        Set loOut = wsOut.ListObjects.Add(xlSrcRange, outRng, , xlYes)
        loOut.Name = "tbl_OutputFutureEvents"
    End If

    ' Basic formatting
    wsOut.Columns.AutoFit

cleanExit:
    Application.Calculation = calcMode
    Application.EnableEvents = True
    Application.ScreenUpdating = True
    Exit Sub

fail:
    Resume cleanExit
End Sub

'========================
' Helpers
'========================
Private Function GetOrCreateSheet(ByVal sheetName As String) As Worksheet
    On Error Resume Next
    Set GetOrCreateSheet = ThisWorkbook.Worksheets(sheetName)
    On Error GoTo 0
    If GetOrCreateSheet Is Nothing Then
        Set GetOrCreateSheet = ThisWorkbook.Worksheets.Add(After:=ThisWorkbook.Worksheets(ThisWorkbook.Worksheets.count))
        GetOrCreateSheet.name = sheetName
    End If
End Function

Private Function GetTransitDateSafe() As Date
    ' Tries Named Range "TransitDate" first; falls back to Now.
    On Error GoTo fallback
    Dim nm As name
    Set nm = ThisWorkbook.names("TransitDate")
    If Not nm Is Nothing Then
        If IsDate(nm.RefersToRange.value2) Then
            GetTransitDateSafe = CDate(nm.RefersToRange.value2)
            Exit Function
        End If
    End If
fallback:
    GetTransitDateSafe = Now
End Function

Public Function FindTableAcrossWorkbook(ByVal tableName As String, Optional ByVal wb As Workbook = Nothing) As ListObject
    Dim w As Worksheet, lo As ListObject

    If wb Is Nothing Then Set wb = ThisWorkbook

    For Each w In wb.Worksheets
        For Each lo In w.ListObjects
            If StrComp(lo.Name, tableName, vbTextCompare) = 0 Then
                Set FindTableAcrossWorkbook = lo
                Exit Function
            End If
        Next lo
    Next w

    Set FindTableAcrossWorkbook = Nothing
End Function


