Option Explicit

' ========= CONFIG =========
Private Const DATA_BLOCK_ADDR As String = "GG21:GL28"

Private Const ROW_PLANET   As Long = 1
Private Const ROW_RL       As Long = 2
Private Const ROW_NL       As Long = 3
Private Const ROW_NLOFNL   As Long = 4
Private Const ROW_SL       As Long = 5
Private Const ROW_NLOFSSL  As Long = 6
Private Const ROW_SSL      As Long = 7
Private Const ROW_NLOFSL   As Long = 8

' =====================================================================
'  VimDasaTbl CACHE + WINDOW LOOKUP (unique names to avoid collisions)
'  Used by ConnSummaryCore to compute StartRow/EndRow/StartDate/EndDate/Durations
' =====================================================================

' === Global cache for VimDasaTbl ===
Public CAS_VimDasaArr As Variant
Public CAS_VimDasaRowCount As Long
Public CAS_VimDasaCol As Object
Public CAS_VimDasaLoaded As Boolean

Private Function CAS_FindTableAcrossWorkbook(ByVal tableName As String, Optional ByRef wsFound As Worksheet) As ListObject
    Dim ws As Worksheet
    Dim lo As ListObject

    For Each ws In ThisWorkbook.Worksheets
        On Error Resume Next
        Set lo = ws.ListObjects(tableName)
        On Error GoTo 0

        If Not lo Is Nothing Then
            Set wsFound = ws
            Set CAS_FindTableAcrossWorkbook = lo
            Exit Function
        End If
    Next ws

    Set CAS_FindTableAcrossWorkbook = Nothing
End Function

Public Sub CAS_LoadVimDasaCache(Optional ByVal tableName As String = "VimDasaTbl")
    Dim lo As ListObject
    Dim lc As ListColumn
    Dim wsFound As Worksheet

    If CAS_VimDasaLoaded Then Exit Sub

    Set lo = CAS_FindTableAcrossWorkbook(tableName, wsFound)
    If lo Is Nothing Then Err.Raise 5, , tableName & " not found in any worksheet."

    If lo.DataBodyRange Is Nothing Then Err.Raise 5, , tableName & " has no rows (DataBodyRange is Nothing)."

    CAS_VimDasaArr = lo.DataBodyRange.Value
    CAS_VimDasaRowCount = UBound(CAS_VimDasaArr, 1)

    Set CAS_VimDasaCol = CreateObject("Scripting.Dictionary")
    CAS_VimDasaCol.CompareMode = vbTextCompare

    For Each lc In lo.ListColumns
        CAS_VimDasaCol(lc.Name) = lc.Index
    Next lc

    CAS_VimDasaLoaded = True
End Sub

Private Function CAS_CanonName(ByVal s As String) As String
    ' Normalize header names to handle extra spaces, underscores, hyphens, NBSP, etc.
    s = CStr(s)
    s = Replace(s, ChrW(160), " ")
    s = Trim$(s)
    s = Replace(s, " ", "")
    s = Replace(s, "_", "")
    s = Replace(s, "-", "")
    s = Replace(s, ".", "")
    s = UCase$(s)
    CAS_CanonName = s
End Function

Private Function CAS_GetColIndexAny(ByVal dict As Object, ByVal names As Variant) As Long
    Dim i As Long, nm As String, key As Variant
    Dim canon As String, keyCanon As String

    ' 1) Direct lookup first
    For i = LBound(names) To UBound(names)
        nm = CStr(names(i))
        If dict.Exists(nm) Then
            CAS_GetColIndexAny = CLng(dict(nm))
            Exit Function
        End If
    Next i

    ' 2) Canonical lookup (robust against minor header differences)
    For i = LBound(names) To UBound(names)
        canon = CAS_CanonName(CStr(names(i)))
        If Len(canon) > 0 Then
            For Each key In dict.Keys
                keyCanon = CAS_CanonName(CStr(key))
                If keyCanon = canon Then
                    CAS_GetColIndexAny = CLng(dict(key))
                    Exit Function
                End If
            Next key
        End If
    Next i

    CAS_GetColIndexAny = 0
End Function

Private Function CAS_Pl2(ByVal v As Variant) As String
    Dim s As String
    s = Trim$(CStr(v))
    If Len(s) >= 2 Then
        CAS_Pl2 = UCase$(Left$(s, 2))
    Else
        CAS_Pl2 = UCase$(s)
    End If
End Function

Private Function CAS_SamePl(ByVal a As Variant, ByVal b As Variant) As Boolean
    CAS_SamePl = (StrComp(CAS_Pl2(a), CAS_Pl2(b), vbTextCompare) = 0)
End Function


' Wrapper used by ConnSummaryCore: reads MD..DEH from GG20:GL20 on the caller sheet.
Public Function CAS_GetDasaWindowCachedFromRange(ByVal LevelsConnected As Long) As Variant
    Dim ws As Worksheet
    If TypeOf Application.Caller Is Range Then
        Set ws = Application.Caller.Worksheet
    Else
        Set ws = ActiveSheet
    End If

    If Not CAS_VimDasaLoaded Then CAS_LoadVimDasaCache "VimDasaTbl"

    CAS_GetDasaWindowCachedFromRange = CAS_GetDasaWindow_Internal( _
        LevelsConnected, _
        CStr(ws.Range("GG20").Value), _
        CStr(ws.Range("GH20").Value), _
        CStr(ws.Range("GI20").Value), _
        CStr(ws.Range("GJ20").Value), _
        CStr(ws.Range("GK20").Value), _
        CStr(ws.Range("GL20").Value) _
    )
End Function

' Core window finder: returns Array(rStart, rEnd, dStart, dEnd, durDays, durYears, durMonths)
Public Function CAS_GetDasaWindow_Internal( _
    ByVal LevelsConnected As Long, _
    ByVal md As String, _
    ByVal ad As String, _
    ByVal pd As String, _
    ByVal su As String, _
    ByVal prana As String, _
    ByVal deh As String _
) As Variant

    Dim mdCol As Long, adCol As Long, pdCol As Long
    Dim suCol As Long, prCol As Long, dehCol As Long
    Dim dateCol As Long

    If LevelsConnected <= 0 Then
        CAS_GetDasaWindow_Internal = Array(0, 0, 0, 0, 0#, 0#, 0#)
        Exit Function
    End If

    If Not CAS_VimDasaLoaded Then CAS_LoadVimDasaCache "VimDasaTbl"

    ' Accept either MD/AD/PD/SU/PRANA/DEH columns OR Dasa/Bhukti/Antara/Sukshma/Prana/Deha naming.
    mdCol = CAS_GetColIndexAny(CAS_VimDasaCol, Array("MD", "Dasa"))
    adCol = CAS_GetColIndexAny(CAS_VimDasaCol, Array("AD", "Bhukti"))
    pdCol = CAS_GetColIndexAny(CAS_VimDasaCol, Array("PD", "Antara"))
    suCol = CAS_GetColIndexAny(CAS_VimDasaCol, Array("SU", "Sukshma"))
    prCol = CAS_GetColIndexAny(CAS_VimDasaCol, Array("PRANA", "Prana"))
    dehCol = CAS_GetColIndexAny(CAS_VimDasaCol, Array("DEH", "Deha"))

    ' Date column (support multiple common header names)
    dateCol = CAS_GetColIndexAny(CAS_VimDasaCol, Array("DasaDate", "Dasa Start Date", "DasaStartDate", "StartDate", "DasaStart", "Dasa Start", "Date"))

    If mdCol = 0 Or adCol = 0 Or pdCol = 0 Or suCol = 0 Or prCol = 0 Or dehCol = 0 Or dateCol = 0 Then
        CAS_GetDasaWindow_Internal = Array(0, 0, 0, 0, 0#, 0#, 0#)
        Exit Function
    End If

    Dim useMD As Boolean, useAD As Boolean, usePD As Boolean
    Dim useSU As Boolean, usePR As Boolean, useDEH As Boolean
    useMD = (LevelsConnected >= 1)
    useAD = (LevelsConnected >= 2)
    usePD = (LevelsConnected >= 3)
    useSU = (LevelsConnected >= 4)
    usePR = (LevelsConnected >= 5)
    useDEH = (LevelsConnected >= 6)

    Dim r As Long
    Dim rStart As Long, rEnd As Long
    rStart = 0: rEnd = 0

    For r = 1 To CAS_VimDasaRowCount
        If (Not useMD Or StrComp(CStr(CAS_VimDasaArr(r, mdCol)), md, vbTextCompare) = 0) _
        And (Not useAD Or StrComp(CStr(CAS_VimDasaArr(r, adCol)), ad, vbTextCompare) = 0) _
        And (Not usePD Or StrComp(CStr(CAS_VimDasaArr(r, pdCol)), pd, vbTextCompare) = 0) _
        And (Not useSU Or StrComp(CStr(CAS_VimDasaArr(r, suCol)), su, vbTextCompare) = 0) _
        And (Not usePR Or StrComp(CStr(CAS_VimDasaArr(r, prCol)), prana, vbTextCompare) = 0) _
        And (Not useDEH Or StrComp(CStr(CAS_VimDasaArr(r, dehCol)), deh, vbTextCompare) = 0) Then

            If rStart = 0 Then rStart = r
            rEnd = r
        End If
    Next r

    If rStart = 0 Then
        CAS_GetDasaWindow_Internal = Array(0, 0, 0, 0, 0#, 0#, 0#)
        Exit Function
    End If

    Dim dStart As Date, dEnd As Date
    dStart = CDate(CAS_VimDasaArr(rStart, dateCol))

    If rEnd < CAS_VimDasaRowCount Then
        dEnd = CDate(CAS_VimDasaArr(rEnd + 1, dateCol))
    Else
        dEnd = dStart
    End If

    Dim durDays As Double, durYears As Double, durMonths As Double
    durDays = CDbl(dEnd - dStart)
    durYears = durDays / 365.2425
    durMonths = durDays / 30.436875

    CAS_GetDasaWindow_Internal = Array(rStart, rEnd, dStart, dEnd, durDays, durYears, durMonths)
End Function


' ========= PLANETS =========
Private Function PlanetList() As Variant
    PlanetList = Array("Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke")
End Function

' ========= TOKEN PARSER =========
Private Function HasTokenSafe(ByVal cellText As String, ByVal want As String) As Boolean
    Dim s As String, A As Variant, i As Long
    s = UCase$(Trim$(cellText)): want = UCase$(Trim$(want))
    If Len(s) = 0 Or Len(want) = 0 Then Exit Function
    s = Replace(s, "(", ",")
    s = Replace(s, ")", ",")
    s = Replace(s, ";", ",")
    s = Replace(s, " ", "")
    Do While InStr(s, ",,") > 0: s = Replace(s, ",,", ","): Loop
    If Left$(s, 1) = "," Then s = mid$(s, 2)
    If Right$(s, 1) = "," Then s = Left$(s, Len(s) - 1)
    A = Split(s, ",")
    For i = LBound(A) To UBound(A)
        If Trim$(A(i)) = want Then HasTokenSafe = True: Exit Function
    Next i
End Function

' ========= OLD COUNT HELPERS (kept for compatibility) =========
Private Function AnyHitForPlanetInColumn(ByVal dataR As Range, ByVal colIdx As Long, ByVal Planet As String) As Long
    Dim R As Long
    For R = 1 To dataR.rows.count
        If HasTokenSafe(CStr(dataR.Cells(R, colIdx).Value), Planet) Then AnyHitForPlanetInColumn = 1: Exit Function
    Next R
End Function

Private Function CountPlanetInRow(ByVal dataR As Range, ByVal rowIdx As Long, ByVal Planet As String) As Long
    Dim c As Long
    If rowIdx < 1 Or rowIdx > dataR.rows.count Then Exit Function
    For c = 1 To dataR.Columns.count
        If HasTokenSafe(CStr(dataR.Cells(rowIdx, c).Value), Planet) Then CountPlanetInRow = CountPlanetInRow + 1
    Next c
End Function

Private Function CountPlanetTotal(ByVal dataR As Range, ByVal Planet As String) As Long
    Dim R As Long, c As Long
    For R = 1 To dataR.rows.count
        For c = 1 To dataR.Columns.count
            If HasTokenSafe(CStr(dataR.Cells(R, c).Value), Planet) Then CountPlanetTotal = CountPlanetTotal + 1
        Next c
    Next R
End Function

Private Function CountPlanet_NLType(ByVal dataR As Range, ByVal Planet As String) As Long
    CountPlanet_NLType = _
          CountPlanetInRow(dataR, ROW_NL, Planet) + _
          CountPlanetInRow(dataR, ROW_NLOFNL, Planet) + _
          CountPlanetInRow(dataR, ROW_NLOFSL, Planet) + _
          CountPlanetInRow(dataR, ROW_NLOFSSL, Planet)
End Function

' ========= GRID TABLE LOOKUP (OPTIMIZED / CACHED) =========

Private Function FindTableAcrossWorkbook(ByVal tableName As String) As ListObject
    Dim wb As Workbook, ws As Worksheet, lo As ListObject
    If TypeOf Application.Caller Is Range Then
        Set wb = Application.Caller.Parent.Parent
    Else
        Set wb = ThisWorkbook
    End If
    For Each ws In wb.Worksheets
        On Error Resume Next
        Set lo = ws.ListObjects(tableName)
        On Error GoTo 0
        If Not lo Is Nothing Then
            Set FindTableAcrossWorkbook = lo
            Exit Function
        End If
    Next ws
End Function

' Cached lookup: PlTbl + planet -> row + score column -> col index
Private Function ScoreFromPlTbl(ByVal Planet As String, ByVal scoreColumnName As String) As Variant
    Static lo As ListObject
    Static headers As Object
    Static planetRow As Object      ' "Su","Mo",... -> row index
    Static scoreCols As Object      ' "WTDSCORE", "WTDSCORE_NOSSL", "SCORE"... -> col index
    Static cachedWB As String

    Dim wb As Workbook
    Dim iPlCol As Long, R As Long
    Dim Data As Variant
    Dim key As String
    Dim colScore As Long, rowIdx As Long

    On Error GoTo fail

    ' Decide which workbook to use
    If TypeOf Application.Caller Is Range Then
        Set wb = Application.Caller.Parent.Parent
    Else
        Set wb = ThisWorkbook
    End If

    ' Rebuild cache if workbook changed or not initialised
    If lo Is Nothing Or cachedWB <> wb.name Then
        Set lo = FindTableAcrossWorkbook("PlTbl")
        If lo Is Nothing Then GoTo fail

        Set headers = MapHeaders(lo.HeaderRowRange)

        ' Planet column
        iPlCol = HCol(headers, Array("PLANET", "PLNT"))
        If iPlCol = 0 Then GoTo fail

        ' Build planet -> row dict
        Set planetRow = CreateObject("Scripting.Dictionary")
        planetRow.CompareMode = vbTextCompare

        Data = lo.DataBodyRange.Value
        For R = 1 To UBound(Data, 1)
            key = ProperPlanetName(Data(R, iPlCol))
            If Len(key) > 0 Then
                planetRow(key) = R    ' last wins if duplicate
            End If
        Next R

        ' Init score column cache
        Set scoreCols = CreateObject("Scripting.Dictionary")
        scoreCols.CompareMode = vbTextCompare

        cachedWB = wb.name
    End If

    ' Find or reuse cached score column
    key = Trim$(UCase$(scoreColumnName))
    If Not scoreCols.Exists(key) Then
        colScore = HCol(headers, Array(scoreColumnName))
        If colScore = 0 Then GoTo fail
        scoreCols(key) = colScore
    Else
        colScore = CLng(scoreCols(key))
    End If

    ' Lookup row for planet
    key = ProperPlanetName(Planet)
    If Not planetRow.Exists(key) Then GoTo fail
    rowIdx = CLng(planetRow(key))

    ScoreFromPlTbl = lo.DataBodyRange.Cells(rowIdx, colScore).Value
    Exit Function

fail:
    ScoreFromPlTbl = CVErr(xlErrNA)
End Function

Private Function Score_WTDSCORE(ByVal Planet As String) As Variant
    Score_WTDSCORE = ScoreFromPlTbl(Planet, "WTDSCORE")
End Function

Private Function Score_WTDSCORE_NOSSL(ByVal Planet As String) As Variant
    Score_WTDSCORE_NOSSL = ScoreFromPlTbl(Planet, "WTDSCORE_NOSSL")
End Function

Private Function Score_SCORE(ByVal Planet As String) As Variant
    Dim headers As Variant, i As Long, v As Variant
    headers = Array("SCORE", "SCORE_N", "SCORE_NORM", "SCORE_RAW")
    For i = LBound(headers) To UBound(headers)
        v = ScoreFromPlTbl(Planet, CStr(headers(i)))
        If Not IsError(v) Then
            Score_SCORE = v
            Exit Function
        End If
    Next i
    Score_SCORE = CVErr(xlErrNA)
End Function

Private Function ComparePriority(A() As Variant, i As Long, j As Long) As Long
    Dim keys As Variant, k As Variant, vi As Double, vj As Double
    keys = Array(7, 8, 9, 10, 11, 12)  ' LevelsConnected, Freqs, Scores...
    For Each k In keys
        vi = SafeVal(A(i, k))
        vj = SafeVal(A(j, k))
        If vi > vj Then ComparePriority = 1: Exit Function
        If vi < vj Then ComparePriority = -1: Exit Function
    Next k
    ComparePriority = 0
End Function

' ========= RESET PICK ROW =========

Public Sub ResetAndReloadPicks()
    Dim ws As Worksheet
    Dim wasProt As Boolean
    Dim prevScreen As Boolean
    Dim prevEvents As Boolean
    Dim prevCalc As XlCalculation

    On Error Resume Next
    Set ws = ActiveSheet
    If ws Is Nothing Then Exit Sub

    ' Save app state
    prevScreen = Application.ScreenUpdating
    prevEvents = Application.EnableEvents
    prevCalc = Application.Calculation

    wasProt = ws.ProtectContents
    If wasProt Then ws.Unprotect

    ' --- HARD QUIET ZONE ---
    Application.ScreenUpdating = False
    Application.EnableEvents = False
    Application.Calculation = xlCalculationManual
    On Error GoTo Cleanup

    ' Clear GG20:GL20 (MD through DEH)
    ws.Range("GG20:GL20").ClearContents

    ' Reload dropdowns and auto defaults
    SetupRollup_FY20_to_GE20

Cleanup:
    ' Restore app state
    Application.Calculation = prevCalc
    Application.EnableEvents = prevEvents
    Application.ScreenUpdating = prevScreen

    If wasProt Then
        On Error Resume Next
        ws.Protect
        On Error GoTo 0
    End If
End Sub

' ========= Helpers required by Reset/Setup/... =========

Public Function MapHeaders(ByVal headerRow As Range) As Object
    Dim D As Object: Set D = CreateObject("Scripting.Dictionary")
    Dim baseCol As Long, c As Range, key As String
    baseCol = headerRow.Cells(1, 1).Column
    For Each c In headerRow.Cells
        key = Trim$(UCase$(CStr(c.Value)))
        If Len(key) > 0 Then D(key) = c.Column - baseCol + 1
    Next c
    Set MapHeaders = D
End Function

Public Function HCol(ByVal headers As Object, ByVal names As Variant) As Long
    Dim i As Long, k As String
    For i = LBound(names) To UBound(names)
        k = Trim$(UCase$(CStr(names(i))))
        If headers.Exists(k) Then
            HCol = CLng(headers(k))
            Exit Function
        End If
    Next i
    HCol = 0
End Function

Private Function SafeVal(ByVal v As Variant) As Double
    On Error Resume Next
    If IsError(v) Then
        SafeVal = 0
    ElseIf IsNumeric(v) Then
        SafeVal = CDbl(v)
    Else
        SafeVal = Val(CStr(v))
    End If
End Function

Public Function SafeDbl(ByVal v As Variant) As Double
    On Error Resume Next
    If IsNumeric(v) Then SafeDbl = CDbl(v) Else SafeDbl = 0
    On Error GoTo 0
End Function

'

' ========= Pending MD picker =========
Public Function FirstPendingDasaLord(ByVal dasaTableRange As Range) As String
    On Error GoTo done
    Dim Data As Variant, headers As Object
    Data = dasaTableRange.Value
    Set headers = MapHeaders(dasaTableRange.rows(1))

    Dim iOrder&, iDur&, iLord&
    iOrder = HCol(headers, Array("DASAORDER", "DasaOrder", "DASA ORDER", "ORDER", "DASA OR", "Dasa Order"))
    iDur = HCol(headers, Array("DASA DURATION LEFT", "Dasa Duration Left", "BALANCE", "REMAINING"))
    iLord = HCol(headers, Array("DASALORD", "DASA LORD", "PLANET", "Planet"))

    If iOrder = 0 Or iLord = 0 Then Exit Function

    Dim R As Long, bestOrd As Double, pick As String, ord As Double, dur As String
    bestOrd = 1E+30

    For R = 2 To UBound(Data, 1)
        ord = Val(Data(R, iOrder))
        If iDur > 0 Then
            dur = Trim$(CStr(Data(R, iDur)))
            If Len(dur) > 0 And Left$(dur, 1) = "0" Then GoTo nextRow
        End If
        If ord > 0 And ord < bestOrd Then
            bestOrd = ord
            pick = CStr(Data(R, iLord))
        End If
nextRow:
    Next R

    If Len(pick) > 0 Then FirstPendingDasaLord = ProperPlanetName(pick)
done:
End Function

' --- bundle Bhukti + Antra for a given Dasa lord ---
Public Function BhuktiToAntraBundle( _
    ByVal dasaLord As String, _
    ByVal gridRange As Range, _
    ByVal bhuktiCount As Long, _
    ByVal antraCount As Long, _
    ByVal showScores As Boolean) As String

    On Error GoTo done
    Dim lordU As String, bhList As String, bhFirst As String, anList As String

    lordU = UCase$(Trim$(CStr(dasaLord)))
    If Len(lordU) = 0 Then Exit Function

    bhList = BhuktiPickList2(lordU, gridRange, bhuktiCount, showScores)
    If Len(Trim$(bhList)) = 0 Then Exit Function

    bhFirst = FirstToken(bhList)
    If Len(bhFirst) = 0 Then Exit Function

    anList = AntraPickList2(UCase$(bhFirst), gridRange, antraCount, showScores)

    BhuktiToAntraBundle = "Bhukti: " & bhList & " | Antra(" & bhFirst & "): " & anList
done:
End Function

Public Function FirstToken(ByVal csv As String) As String
    Dim s As String, p As String, k As Long
    s = Trim$(CStr(csv))
    If Len(s) = 0 Then Exit Function
    k = InStr(s, ",")
    If k > 0 Then p = Left$(s, k - 1) Else p = s
    p = Trim$(p)
    p = UCase$(Left$(p, 1)) & LCase$(mid$(p, 2, 1))
    FirstToken = p
End Function

Public Function NthToken(ByVal csv As String, ByVal n As Long) As String
    Dim A() As String, t As String
    If n <= 0 Then Exit Function
    A = Split(Trim$(CStr(csv)), ",")
    If UBound(A) < 0 Or n - 1 > UBound(A) Then Exit Function
    t = Trim$(A(n - 1))
    NthToken = UCase$(Left$(t, 1)) & LCase$(mid$(t, 2, 1))
End Function

Private Function FormatOriginList(ByRef names() As String, ByRef scores() As Double, ByVal n As Long, ByVal maxOut As Long) As String
    Dim i As Long, upTo As Long, parts() As String
    If n <= 0 Then Exit Function
    upTo = IIf(maxOut > 0 And maxOut < n, maxOut, n)
    ReDim parts(1 To upTo)
    For i = 1 To upTo
        parts(i) = ProperPlanetName(names(i - 1)) & " (" & Format$(scores(i - 1), "0.0") & ")"
    Next i
    FormatOriginList = Join(parts, ", ")
    If upTo < n Then FormatOriginList = FormatOriginList & " "
End Function

Private Sub SortDescNamesByScores(ByRef names() As String, ByRef scores() As Double, ByVal n As Long)
    Dim i As Long, j As Long, tS As Double, tN As String
    For i = 0 To n - 2
        For j = i + 1 To n - 1
            If scores(j) > scores(i) Then
                tS = scores(i): scores(i) = scores(j): scores(j) = tS
                tN = names(i): names(i) = names(j): names(j) = tN
            End If
        Next j
    Next i
End Sub

Private Function FormatOriginListAll(ByRef names() As String, ByRef scores() As Double, ByVal n As Long) As String
    Dim i As Long, parts() As String
    If n <= 0 Then Exit Function
    ReDim parts(1 To n)
    For i = 1 To n
        parts(i) = ProperPlanetName(names(i - 1)) & " (" & Format$(scores(i - 1), "0.0") & ")"
    Next i
    FormatOriginListAll = Join(parts, ", ")
End Function

'==============================================================
'   CORE SUMMARY FUNCTION  REQUIRED FOR BATCH ANALYSIS
'==============================================================
Private Function ConnSummaryCore(ByVal ws As Worksheet, _
                                 ByVal dataAddress As String) As Variant
    On Error GoTo fail

    Dim dataR As Range
    Set dataR = ws.Range(dataAddress)

    Dim planets As Variant: planets = PlanetList()
    Dim dataArr As Variant
    dataArr = dataR.Value

    Dim nPlanets As Long
    nPlanets = UBound(planets) - LBound(planets) + 1

    Dim plIndex As Object
    Set plIndex = CreateObject("Scripting.Dictionary")
    plIndex.CompareMode = vbTextCompare

    Dim p As Long
    For p = LBound(planets) To UBound(planets)
        plIndex(UCase$(Left$(planets(p), 2))) = p - LBound(planets)
    Next p

    Dim colHit() As Boolean
    Dim freqTotal() As Long
    Dim freqNLType() As Long

    ReDim colHit(0 To nPlanets - 1, 1 To 6)
    ReDim freqTotal(0 To nPlanets - 1)
    ReDim freqNLType(0 To nPlanets - 1)

    Dim rowsCnt As Long, colsCnt As Long
    rowsCnt = UBound(dataArr, 1)
    colsCnt = UBound(dataArr, 2)

    Dim R As Long, c As Long
    Dim s As String, t As String
    Dim tokens As Variant, idx As Long
    Dim key As String

    For R = 1 To rowsCnt
        For c = 1 To colsCnt
            s = Trim$(CStr(dataArr(R, c)))
            If Len(s) = 0 Then GoTo NextCell

            s = Replace(s, "(", ",")
            s = Replace(s, ")", ",")
            s = Replace(s, ";", ",")
            s = Replace(s, "|", ",")
            s = Replace(s, " ", "")
            Do While InStr(s, ",,") > 0: s = Replace(s, ",,", ","): Loop

            If Left$(s, 1) = "," Then s = mid$(s, 2)
            If Right$(s, 1) = "," Then s = Left$(s, Len(s) - 1)
            If Len(s) = 0 Then GoTo NextCell

            tokens = Split(s, ",")
            For idx = LBound(tokens) To UBound(tokens)
                t = Trim$(CStr(tokens(idx)))
                If Len(t) >= 2 Then
                    key = UCase$(Left$(t, 2))
                    If plIndex.Exists(key) Then
                        p = plIndex(key)

                        freqTotal(p) = freqTotal(p) + 1

                        If R = ROW_NL Or R = ROW_NLOFNL _
                           Or R = ROW_NLOFSSL Or R = ROW_NLOFSL Then
                            freqNLType(p) = freqNLType(p) + 1
                        End If

                        If c >= 1 And c <= 6 Then colHit(p, c) = True
                    End If
                End If
            Next idx

NextCell:
        Next c
    Next R

    Dim raw() As Variant
    ReDim raw(0 To nPlanets - 1, 0 To 19)

    Dim col As Long, cntCols As Long

    For p = 0 To nPlanets - 1
        raw(p, 0) = planets(p)

        ' --- write level flags ---
        For c = 1 To 6
            If colHit(p, c) Then
                raw(p, c) = 1
            Else
                raw(p, c) = 0
            End If
        Next c

        ' --- MD-anchored continuous connectivity (6 levels) ---
        Dim lc As Long
        lc = 0
        If raw(p, 1) = 1 Then
            lc = 1
            For c = 2 To 6
                If raw(p, c) = 1 Then
                    lc = lc + 1
                Else
                    Exit For
                End If
            Next c
        End If

        raw(p, 7) = lc
        raw(p, 8) = freqTotal(p)
        raw(p, 9) = freqNLType(p)
        raw(p, 10) = Score_SCORE(raw(p, 0))
        raw(p, 11) = Score_WTDSCORE(raw(p, 0))
        raw(p, 12) = Score_WTDSCORE_NOSSL(raw(p, 0))
    

        ' --- Dasa window (start/end/duration) based on LevelsConnected ---
        Dim win As Variant
        On Error Resume Next
        win = CAS_GetDasaWindowCachedFromRange(lc)
        On Error GoTo 0
        If IsArray(win) Then
            raw(p, 13) = CLng(win(0))
            raw(p, 14) = CLng(win(1))
            raw(p, 15) = win(2)
            raw(p, 16) = win(3)
            raw(p, 17) = CDbl(win(4))
            raw(p, 18) = CDbl(win(5))
            raw(p, 19) = CDbl(win(6))
        Else
            raw(p, 13) = 0
            raw(p, 14) = 0
            raw(p, 15) = 0
            raw(p, 16) = 0
            raw(p, 17) = 0
            raw(p, 18) = 0
            raw(p, 19) = 0
        End If
Next p

    Dim i As Long, j As Long, k As Long, tmp As Variant
    For i = LBound(raw) To UBound(raw) - 1
        For j = i + 1 To UBound(raw)
            If ComparePriority(raw, i, j) < 0 Then
                For k = 0 To 19
                    tmp = raw(i, k)
                    raw(i, k) = raw(j, k)
                    raw(j, k) = tmp
                Next k
            End If
        Next j
    Next i

    Dim out() As Variant
    ReDim out(0 To nPlanets, 0 To 19)

    Dim header As Variant
    header = Array("Planet", "MD", "AD", "PD", "SU", "PRANA", "DEH", _
                   "LevelsConnected", "Freq_Total", "Freq_NLType", _
                   "Score", "WTDSCORE", "WTDSCORE_NOSSL", _
                   "StartRow", "EndRow", "StartDate", "EndDate", _
                   "DurDays", "DurYears", "DurMonths")

    For col = 0 To UBound(header)
        out(0, col) = header(col)
    Next col

    For i = 0 To nPlanets - 1
        For col = 0 To 19
            out(i + 1, col) = raw(i, col)
        Next col
    Next i

    ConnSummaryCore = out
    Exit Function

fail:
    ConnSummaryCore = CVErr(xlErrValue)
End Function

Public Function ConnSummary_All_WithNLType_AndScores() As Variant
    Dim ws As Worksheet
    If TypeOf Application.Caller Is Range Then
        Set ws = Application.Caller.Worksheet
    Else
        Set ws = ActiveSheet
    End If
    ConnSummary_All_WithNLType_AndScores = ConnSummaryCore(ws, DATA_BLOCK_ADDR)
End Function

Public Function FixTiny(v As Variant, Optional roundTo2 As Boolean = False) As Variant
    If IsNumeric(v) Then
        Dim x As Double
        x = CDbl(v)

        If Abs(x) < 0.0000001 Then
            FixTiny = 0
            Exit Function
        End If

        If roundTo2 Then
            FixTiny = Round(x, 2)
        Else
            FixTiny = x
        End If
    Else
        FixTiny = v
    End If
End Function




' ---------- Vimshottari helpers ----------

Private Function VimPlanetOrder() As Variant
    VimPlanetOrder = Array("Ke", "Ve", "Su", "Mo", "Ma", "Ra", "Ju", "Sa", "Me")
End Function

Private Function VimPlanetYears(ByVal PL As String) As Double
    PL = ProperPlanetName(PL)
    Select Case PL
        Case "Ke": VimPlanetYears = 7
        Case "Ve": VimPlanetYears = 20
        Case "Su": VimPlanetYears = 6
        Case "Mo": VimPlanetYears = 10
        Case "Ma": VimPlanetYears = 7
        Case "Ra": VimPlanetYears = 18
        Case "Ju": VimPlanetYears = 16
        Case "Sa": VimPlanetYears = 19
        Case "Me": VimPlanetYears = 17
        Case Else: VimPlanetYears = 0
    End Select
End Function

Private Function VimIndex(ByVal PL As String) As Long
    Dim arr As Variant, i As Long
    PL = ProperPlanetName(PL)
    arr = VimPlanetOrder()
    For i = LBound(arr) To UBound(arr)
        If arr(i) = PL Then
            VimIndex = i
            Exit Function
        End If
    Next i
    VimIndex = -1
End Function
Public Function VimsottariEventDate( _
    ByVal mdStart As Date, _
    ByVal mdEnd As Date, _
    ByVal mdLord As String, _
    Optional ByVal adLord As String = "", _
    Optional ByVal pdLord As String = "", _
    Optional ByVal suLord As String = "", _
    Optional ByVal prLord As String = "", _
    Optional ByVal dehLord As String = "", _
    Optional ByVal which As String = "MID") As Variant

    On Error GoTo fail

    Dim levelLords(1 To 5) As String
    Dim currStart As Date, currEnd As Date, currLen As Double
    Dim currLord As String
    Dim arrOrder As Variant
    Dim iLevel As Long, targetLord As String
    Dim iStart As Long, i As Long
    Dim segLenDays(0 To 8) As Double
    Dim totalDays As Double
    Dim p As String
    Dim offset As Double
    Dim found As Boolean

    ' --- load level lords ---
    levelLords(1) = adLord
    levelLords(2) = pdLord
    levelLords(3) = suLord
    levelLords(4) = prLord
    levelLords(5) = dehLord

    ' --- initial MD window ---
    currStart = mdStart
    currEnd = mdEnd
    currLen = CDbl(currEnd - currStart)
    currLord = ProperPlanetName(mdLord)

    If currLen <= 0 Then GoTo fail
    If VimPlanetYears(currLord) = 0 Then GoTo fail

    arrOrder = VimPlanetOrder()

    ' --- go down AD -> PD -> SU -> PR -> DEH ---
    For iLevel = 1 To 5

        targetLord = ProperPlanetName(levelLords(iLevel))
        If Len(targetLord) = 0 Then Exit For      ' no deeper level

        iStart = VimIndex(currLord)
        If iStart < 0 Then GoTo fail

        ' build 9 sub-segments
        totalDays = 0
        For i = 0 To 8
            p = arrOrder((iStart + i) Mod 9)
            segLenDays(i) = currLen * (VimPlanetYears(p) / 120#)
            totalDays = totalDays + segLenDays(i)
        Next i

        ' scale to match current length exactly (no separate scale variable)
        If totalDays <> 0 Then
            For i = 0 To 8
                segLenDays(i) = segLenDays(i) * currLen / totalDays
            Next i
        End If

        ' find the segment for targetLord
        offset = 0
        found = False

        For i = 0 To 8
            p = arrOrder((iStart + i) Mod 9)
            If p = targetLord Then
                currStart = currStart + offset
                currLen = segLenDays(i)
                currEnd = currStart + currLen
                currLord = targetLord
                found = True
                Exit For
            Else
                offset = offset + segLenDays(i)
            End If
        Next i

        If Not found Then GoTo fail

    Next iLevel

    ' --- return requested date ---
    Select Case UCase$(which)
        Case "START": VimsottariEventDate = currStart
        Case "END":   VimsottariEventDate = currEnd
        Case Else    ' MID
            VimsottariEventDate = currStart + currLen / 2#
    End Select
    Exit Function

fail:
    VimsottariEventDate = CVErr(xlErrNA)
End Function



' ---------- MD window from DasaTable + wrapper ----------

Private Function MDWindowFromDasaTable( _
    ByVal mdLord As String, _
    ByRef mdStart As Date, _
    ByRef mdEnd As Date) As Boolean

    Dim lo As ListObject
    Dim headers As Object
    Dim iLord&, iStart&, iEnd&, R As Long
    Dim Data As Variant, PL As String

    mdLord = ProperPlanetName(mdLord)

    Set lo = FindTableAcrossWorkbook("DasaTable")
    If lo Is Nothing Then Exit Function

    Set headers = MapHeaders(lo.HeaderRowRange)

    iLord = HCol(headers, Array("DASALORD", "DASA LORD", "PLANET", "Planet"))
    iStart = HCol(headers, Array("DASASTART", "STARTDATE", "DASASTART"))
    iEnd = HCol(headers, Array("DASAEND", "ENDDATE", "DASAEND"))

    If iLord = 0 Or iStart = 0 Or iEnd = 0 Then Exit Function

    Data = lo.DataBodyRange.Value
    For R = 1 To UBound(Data, 1)
        PL = ProperPlanetName(CStr(Data(R, iLord)))
        If PL = mdLord Then
            If IsDate(Data(R, iStart)) And IsDate(Data(R, iEnd)) Then
                mdStart = CDate(Data(R, iStart))
                mdEnd = CDate(Data(R, iEnd))
                MDWindowFromDasaTable = True
                Exit Function
            End If
        End If
    Next R
End Function

Public Function DasaEventDateFromTable( _
    ByVal mdLord As String, _
    ByVal adLord As String, _
    ByVal pdLord As String, _
    ByVal suLord As String, _
    ByVal prLord As String, _
    ByVal dehLord As String, _
    Optional ByVal which As String = "MID") As Variant

    Dim mdStart As Date, mdEnd As Date

    If Not MDWindowFromDasaTable(mdLord, mdStart, mdEnd) Then
        DasaEventDateFromTable = CVErr(xlErrNA)
        Exit Function
    End If

    DasaEventDateFromTable = VimsottariEventDate( _
        mdStart, mdEnd, mdLord, adLord, pdLord, suLord, prLord, dehLord, which)
End Function

Public Sub BatchAnalyze_MD_Combinations_Scaled()
    Const GRID_SHEET_NAME As String = "CIL"
    Const COMB_SHEET_NAME As String = "MD_Combinations"
    Const OUT_SHEET_NAME  As String = "MD_Combo_Analysis_Scaled"
    Const PICK_ADDR       As String = "GG20:GL20"

    ' === FILTER CONFIG ===
    Const MIN_LEVELS_CONNECTED As Long = 4      ' focus only on Levels 56
    Const MIN_PROB_NO_SSL      As Double = 70    ' raise this to keep only stronger hits
    Const MIN_EVENT_YEAR       As Long = 0      ' 0 = no filter, or e.g. 2024
    Const MAX_ROWS_OUTPUT      As Long = 1000  ' hard cap on output rows

    Dim wsGrid As Worksheet, wsComb As Worksheet, wsOut As Worksheet
    Dim cMD As Long, cAD As Long, cPD As Long

    Set wsGrid = ThisWorkbook.Worksheets(GRID_SHEET_NAME)
    Set wsComb = ThisWorkbook.Worksheets(COMB_SHEET_NAME)

    ' Create or clear output sheet
    On Error Resume Next
    Set wsOut = ThisWorkbook.Worksheets(OUT_SHEET_NAME)
    On Error GoTo 0

    If wsOut Is Nothing Then
        Set wsOut = ThisWorkbook.Worksheets.Add(After:=wsComb)
        wsOut.name = OUT_SHEET_NAME
    Else
        wsOut.Cells.ClearContents
    End If

    ' Detect columns in MD_Combinations
    Dim hdr As Object
    Set hdr = MapHeaders(wsComb.rows(1))

    cMD = HCol(hdr, Array("MD"))
    cAD = HCol(hdr, Array("AD"))
    cPD = HCol(hdr, Array("PD"))

    If cMD = 0 Or cAD = 0 Or cPD = 0 Then
        MsgBox "MD_Combinations is missing MD/AD/PD columns.", vbCritical
        Exit Sub
    End If

    ' Header
    wsOut.Range("A1").Resize(1, 22).Value = Array( _
        "SeqRow", "MD", "AD", "PD", "SU", "PRANA", "DEH", _
        "Planet", "LevelsConnected", "Freq_Total", "Freq_NLType", _
        "Score", "WTDSCORE", "WTDSCORE_NOSSL", _
        "ProbScore_SSL", "ProbScore_NoSSL", "Delta_SSL", "Rank", _
        "EventStart", "EventEnd", "EventDate", "EventDurationDays")

    Dim lastRow As Long
    lastRow = wsComb.Cells(wsComb.rows.count, cMD).End(xlUp).row

    Dim pickRow As Range
    Set pickRow = wsGrid.Range(PICK_ADDR)

    Dim arrSummary As Variant
    Dim outRow As Long
    outRow = 2

    Application.ScreenUpdating = False
    Application.EnableEvents = False
    Application.Calculation = xlCalculationManual

    Dim R As Long, i As Long
    Dim lvl As Double, NLfreq As Double, Totfreq As Double
    Dim wtd As Double, wtdNoSSL As Double
    Dim pSSL As Double, pNoSSL As Double, dSSL As Double
    Dim planetScore As Double

    Dim mdLord As String, adLord As String, pdLord As String
    Dim suLord As String, prLord As String, dehLord As String
    Dim depth As Long

    Dim passMD As String, passAD As String, passPD As String
    Dim passSU As String, passPR As String, passDEH As String

    Dim evStart As Variant, evEnd As Variant, evMid As Variant
    Dim durDays As Variant

    Dim planets As Variant
    planets = PlanetList()

    Dim iSU As Long, iPR As Long, iDEH As Long
    Dim stopAll As Boolean

    For R = 2 To lastRow

        If stopAll Then Exit For

        If Trim$(CStr(wsComb.Cells(R, cMD).Value)) <> "" Then

            mdLord = ProperPlanetName(wsComb.Cells(R, cMD).Value)
            adLord = ProperPlanetName(wsComb.Cells(R, cAD).Value)
            pdLord = ProperPlanetName(wsComb.Cells(R, cPD).Value)

            ' === TRY ALL 999 combinations for SUPRDEH ===
            For iSU = LBound(planets) To UBound(planets)
                If stopAll Then Exit For
                suLord = planets(iSU)

                For iPR = LBound(planets) To UBound(planets)
                    If stopAll Then Exit For
                    prLord = planets(iPR)

                    For iDEH = LBound(planets) To UBound(planets)
                        If stopAll Then Exit For
                        dehLord = planets(iDEH)

                        ' Drop values into grid
                        pickRow.Cells(1, 1).Value = mdLord
                        pickRow.Cells(1, 2).Value = adLord
                        pickRow.Cells(1, 3).Value = pdLord
                        pickRow.Cells(1, 4).Value = suLord
                        pickRow.Cells(1, 5).Value = prLord
                        pickRow.Cells(1, 6).Value = dehLord

                        wsGrid.Range(DATA_BLOCK_ADDR).Calculate

                        arrSummary = ConnSummaryCore(wsGrid, DATA_BLOCK_ADDR)

                        For i = 1 To UBound(arrSummary, 1)

                            lvl = SafeDbl(arrSummary(i, 7))

                            ' Filter: focus only on LevelsConnected 56
                            If lvl < MIN_LEVELS_CONNECTED Then GoTo NextPlanetLine

                            ' ---- Planet base SCORE (col 10 in summary) ----
                            planetScore = SafeDbl(arrSummary(i, 10))
                            ' Skip planets with non-positive base score
                            If planetScore <= 0 Then GoTo NextPlanetLine

                            NLfreq = SafeDbl(arrSummary(i, 9))
                            Totfreq = SafeDbl(arrSummary(i, 8))

                            wtd = FixTiny(arrSummary(i, 11), True)
                            wtdNoSSL = FixTiny(arrSummary(i, 12), True)

                            pSSL = NLfreq * 2 + Totfreq + wtd * 0.5 + lvl * 0.25
                            pNoSSL = NLfreq * 2 + Totfreq + wtdNoSSL * 0.5 + lvl * 0.25
                            dSSL = pSSL - pNoSSL

                            ' Filter by minimum ProbScore_NoSSL (optional)
                            If pNoSSL < MIN_PROB_NO_SSL Then GoTo NextPlanetLine

                            ' === Compute event depth ===
                            depth = CLng(lvl)
                            If depth < 1 Then depth = 1
                            If depth > 6 Then depth = 6

                            passMD = ""
                            passAD = ""
                            passPD = ""
                            passSU = ""
                            passPR = ""
                            passDEH = ""

                            If depth >= 1 Then passMD = mdLord
                            If depth >= 2 Then passAD = adLord
                            If depth >= 3 Then passPD = pdLord
                            If depth >= 4 Then passSU = suLord
                            If depth >= 5 Then passPR = prLord
                            If depth >= 6 Then passDEH = dehLord

                            evStart = DasaEventDateFromTable(passMD, passAD, passPD, passSU, passPR, passDEH, "START")
                            evEnd = DasaEventDateFromTable(passMD, passAD, passPD, passSU, passPR, passDEH, "END")
                            evMid = DasaEventDateFromTable(passMD, passAD, passPD, passSU, passPR, passDEH, "MID")

                            ' Filter by starting year if configured
                            If MIN_EVENT_YEAR > 0 Then
                                If Not IsDate(evStart) Then GoTo NextPlanetLine
                                If Year(CDate(evStart)) < MIN_EVENT_YEAR Then GoTo NextPlanetLine
                            End If

                            If IsDate(evStart) And IsDate(evEnd) Then
                                durDays = CDbl(evEnd) - CDbl(evStart)
                            Else
                                durDays = vbNullString
                            End If

                            ' === Write output ===
                            wsOut.Cells(outRow, 1).Value = R
                            wsOut.Cells(outRow, 2).Value = mdLord
                            wsOut.Cells(outRow, 3).Value = adLord
                            wsOut.Cells(outRow, 4).Value = pdLord
                            wsOut.Cells(outRow, 5).Value = suLord
                            wsOut.Cells(outRow, 6).Value = prLord
                            wsOut.Cells(outRow, 7).Value = dehLord

                            wsOut.Cells(outRow, 8).Value = arrSummary(i, 0)
                            wsOut.Cells(outRow, 9).Value = FixTiny(lvl)
                            wsOut.Cells(outRow, 10).Value = Totfreq
                            wsOut.Cells(outRow, 11).Value = NLfreq
                            wsOut.Cells(outRow, 12).Value = FixTiny(planetScore, True) ' core SCORE (2dp)
                            wsOut.Cells(outRow, 13).Value = wtd
                            wsOut.Cells(outRow, 14).Value = wtdNoSSL
                            wsOut.Cells(outRow, 15).Value = Round(pSSL, 2)
                            wsOut.Cells(outRow, 16).Value = Round(pNoSSL, 2)
                            wsOut.Cells(outRow, 17).Value = Round(dSSL, 2)

                            wsOut.Cells(outRow, 19).Value = evStart
                            wsOut.Cells(outRow, 20).Value = evEnd
                            wsOut.Cells(outRow, 21).Value = evMid
                            wsOut.Cells(outRow, 22).Value = durDays

                            outRow = outRow + 1

                            ' Hard cap on rows
                            If outRow > MAX_ROWS_OUTPUT + 1 Then
                                stopAll = True
                                Exit For
                            End If

NextPlanetLine:
                        Next i

                    Next iDEH
                Next iPR
            Next iSU

        End If

    Next R

    ' ==== SORT ====
    Dim lastDataRow As Long: lastDataRow = outRow - 1
    If lastDataRow >= 2 Then
        With wsOut.Sort
            .SortFields.Clear
            .SortFields.Add key:=wsOut.Range("S2:S" & lastDataRow), _
                SortOn:=xlSortOnValues, order:=xlAscending
            .SortFields.Add key:=wsOut.Range("P2:P" & lastDataRow), _
                SortOn:=xlSortOnValues, order:=xlDescending
            .SortFields.Add key:=wsOut.Range("Q2:Q" & lastDataRow), _
                SortOn:=xlSortOnValues, order:=xlDescending
            .SetRange wsOut.Range("A1:V" & lastDataRow)
            .header = xlYes
            .Apply
        End With
    End If

    ' ==== RANK ====
    Dim rank As Long: rank = 1
    Dim rowIdx As Long
    For rowIdx = 2 To lastDataRow
        wsOut.Cells(rowIdx, 18).Value = rank
        rank = rank + 1
    Next rowIdx

    wsOut.Columns.AutoFit

    Application.ScreenUpdating = True
    Application.EnableEvents = True
    Application.Calculation = xlCalculationAutomatic
End Sub

Sub Load_MD_Combinations_FromTable()
    Const SRC_SHEET As String = "MD_Combinations"
    Const SRC_TABLE As String = "MD_AD_PD_Table"
    Const OUT_SHEET As String = "MD_Combinations_Full"
    
    Dim wsSrc As Worksheet
    Dim wsOut As Worksheet
    Dim loSrc As ListObject
    Dim rngSrc As Range
    
    On Error GoTo errhand
    
    Set wsSrc = ThisWorkbook.Worksheets(SRC_SHEET)
    Set loSrc = wsSrc.ListObjects(SRC_TABLE)
    Set rngSrc = loSrc.Range
    
    On Error Resume Next
    Set wsOut = ThisWorkbook.Worksheets(OUT_SHEET)
    On Error GoTo 0
    
    If wsOut Is Nothing Then
        Set wsOut = ThisWorkbook.Worksheets.Add(After:=wsSrc)
        wsOut.name = OUT_SHEET
    End If
    
    wsOut.Cells.Clear
    
    rngSrc.Copy
    wsOut.Range("A1").PasteSpecial xlPasteValues
    Application.CutCopyMode = False
    
    Exit Sub

errhand:
    MsgBox "Could not find source table '" & SRC_TABLE & _
           "' on sheet '" & SRC_SHEET & "'.", vbCritical
End Sub



'==========================
'  Bhukti / Antra cache from DasaTable
'==========================
Private Sub EnsureDasaSelectionCache( _
        hasBhSel As Boolean, hasAnSel As Boolean, _
        bhDict As Object, anDict As Object)

    Static inited As Boolean
    Static sHasBh As Boolean
    Static sHasAn As Boolean
    Static sBh As Object
    Static sAn As Object
    
    Dim ws As Worksheet, lo As ListObject
    Dim hdr As Object
    Dim Data As Variant
    Dim R As Long
    Dim iLord As Long, iBh As Long, iAn As Long
    Dim md As String
    Dim txtBh As String, txtAn As String
    Dim parts As Variant, p As Variant
    Dim segs As Variant, seg As Variant
    Dim bStart As Long, bEnd As Long, cPos As Long
    Dim ad As String, pdList As String, pdParts As Variant, pd As Variant
    Dim key As String
    
    If Not inited Then
        Set sBh = CreateObject("Scripting.Dictionary")
        sBh.CompareMode = vbTextCompare
        Set sAn = CreateObject("Scripting.Dictionary")
        sAn.CompareMode = vbTextCompare
        
        sHasBh = False
        sHasAn = False
        
        Set lo = Nothing
        For Each ws In ThisWorkbook.Worksheets
            On Error Resume Next
            Set lo = ws.ListObjects("DasaTable")
            On Error GoTo 0
            If Not lo Is Nothing Then Exit For
        Next ws
        
        If Not lo Is Nothing Then
            Set hdr = MapHeaders(lo.HeaderRowRange)
            iLord = HCol(hdr, Array("DASALORD", "DasaLord", "PLANET", "Plane"))
            iBh = HCol(hdr, Array("BHUKTISELECTION", "BhuktiSelection"))
            iAn = HCol(hdr, Array("ANTRASELECTION", "AntraSelection"))
            
            If iLord > 0 Then
                Data = lo.DataBodyRange.Value
                
                For R = 1 To UBound(Data, 1)
                    md = ProperPlanetName(Data(R, iLord))
                    If Len(md) = 0 Then GoTo nextRow
                    
                    If iBh > 0 Then
                        txtBh = Trim$(CStr(Data(R, iBh)))
                        If Len(txtBh) > 0 Then
                            sHasBh = True
                            parts = Split(txtBh, ",")
                            For Each p In parts
                                key = md & "|" & ProperPlanetName(p)
                                sBh(key) = True
                            Next p
                        End If
                    End If
                    
                    If iAn > 0 Then
                        txtAn = Trim$(CStr(Data(R, iAn)))
                        If Len(txtAn) > 0 Then
                            sHasAn = True
                            segs = Split(txtAn, "|")
                            For Each seg In segs
                                seg = Trim$(CStr(seg))
                                If Len(seg) = 0 Then GoTo NextSeg
                                
                                bStart = InStr(1, seg, "(", vbTextCompare)
                                bEnd = InStr(1, seg, ")", vbTextCompare)
                                cPos = InStr(1, seg, ":", vbTextCompare)
                                
                                If bStart > 0 And bEnd > bStart And cPos > bEnd Then
                                    ad = ProperPlanetName(mid$(seg, bStart + 1, bEnd - bStart - 1))
                                    pdList = mid$(seg, cPos + 1)
                                    pdParts = Split(pdList, ",")
                                    For Each pd In pdParts
                                        key = md & "|" & ad & "|" & ProperPlanetName(pd)
                                        sAn(key) = True
                                    Next pd
                                End If
NextSeg:
                            Next seg
                        End If
                    End If
nextRow:
                Next R
            End If
        End If
        
        inited = True
        sHasBh = (sBh.count > 0)
        sHasAn = (sAn.count > 0)
    End If
    
    hasBhSel = sHasBh
    hasAnSel = sHasAn
    Set bhDict = sBh
    Set anDict = sAn
End Sub

Private Function IsBhuktiAllowed_FromDasaTable(mdLord As String, adLord As String) As Boolean
    Dim hasBh As Boolean, hasAn As Boolean
    Dim bh As Object, an As Object
    Dim key As String
    
    mdLord = ProperPlanetName(mdLord)
    adLord = ProperPlanetName(adLord)
    
    EnsureDasaSelectionCache hasBh, hasAn, bh, an
    
    If Not hasBh Then
        IsBhuktiAllowed_FromDasaTable = True
    Else
        key = mdLord & "|" & adLord
        IsBhuktiAllowed_FromDasaTable = bh.Exists(key)
    End If
End Function

Private Function IsAntraAllowed_FromDasaTable(mdLord As String, adLord As String, pdLord As String) As Boolean
    Dim hasBh As Boolean, hasAn As Boolean
    Dim bh As Object, an As Object
    Dim key As String
    
    mdLord = ProperPlanetName(mdLord)
    adLord = ProperPlanetName(adLord)
    pdLord = ProperPlanetName(pdLord)
    
    EnsureDasaSelectionCache hasBh, hasAn, bh, an
    
    If Not hasAn Then
        IsAntraAllowed_FromDasaTable = True
    Else
        key = mdLord & "|" & adLord & "|" & pdLord
        IsAntraAllowed_FromDasaTable = an.Exists(key)
    End If
End Function

Public Sub BatchAnalyze_MD_Combinations_Full2()
    Const GRID_SHEET_NAME As String = "CIL"
    Const COMB_SHEET_NAME As String = "MD_Combinations_Full"
    Const OUT_SHEET_NAME  As String = "MD_Combo_Analysis"
    Const PICK_ADDR       As String = "GG20:GL20"
    
    Dim wsGrid As Worksheet, wsComb As Worksheet, wsOut As Worksheet
    Dim cMD As Long, cAD As Long, cPD As Long, cSU As Long, cPR As Long, cDEH As Long
    
    Set wsGrid = ThisWorkbook.Worksheets(GRID_SHEET_NAME)
    Set wsComb = ThisWorkbook.Worksheets(COMB_SHEET_NAME)
    
    On Error Resume Next
    Set wsOut = ThisWorkbook.Worksheets(OUT_SHEET_NAME)
    On Error GoTo 0
    If wsOut Is Nothing Then
        Set wsOut = ThisWorkbook.Worksheets.Add(After:=wsComb)
        wsOut.name = OUT_SHEET_NAME
    Else
        wsOut.Cells.ClearContents
    End If
    
    Dim hdr As Object
    Set hdr = MapHeaders(wsComb.rows(1))
    
    cMD = HCol(hdr, Array("MD"))
    cAD = HCol(hdr, Array("AD"))
    cPD = HCol(hdr, Array("PD"))
    cSU = HCol(hdr, Array("SU"))
    cPR = HCol(hdr, Array("PRANA", "PR"))
    cDEH = HCol(hdr, Array("DEH"))
    
    If cMD = 0 Or cAD = 0 Or cPD = 0 Or cSU = 0 Or cPR = 0 Or cDEH = 0 Then
        MsgBox "MD_Combinations_Full is missing MD/AD/PD/SU/PRANA/DEH.", vbCritical
        Exit Sub
    End If
    
    wsOut.Range("A1").Resize(1, 22).Value = Array( _
        "SeqRow", "MD", "AD", "PD", "SU", "PRANA", "DEH", _
        "Planet", "LevelsConnected", "Freq_Total", "Freq_NLType", _
        "Score", "WTDSCORE", "WTDSCORE_NOSSL", _
        "ProbScore_SSL", "ProbScore_NoSSL", "Delta_SSL", "Rank", _
        "EventStart", "EventEnd", "EventDate", "EventDurationDays")
    
    Dim lastRow As Long
    lastRow = wsComb.Cells(wsComb.rows.count, cMD).End(xlUp).row
    
    Dim pickRow As Range
    Set pickRow = wsGrid.Range(PICK_ADDR)
    
    Dim arrSummary As Variant
    Dim outRow As Long
    outRow = 2
    
    Dim minLvl As Long, minProb As Double, minYear As Long, maxRows As Long, mdLimit As Long
    minLvl = CLng(Val(wsGrid.Range("GL10").Value))
    If minLvl <= 0 Then minLvl = 3
    
    minProb = CDbl(Val(wsGrid.Range("GL11").Value))
    minYear = CLng(Val(wsGrid.Range("GL12").Value))
    
    maxRows = CLng(Val(wsGrid.Range("GL13").Value))
    If maxRows <= 0 Then maxRows = 1000000
    
    mdLimit = CLng(Val(wsGrid.Range("GL14").Value))  ' -1 = all pending
    
    Dim allowedMD As Object
    Set allowedMD = CreateObject("Scripting.Dictionary")
    allowedMD.CompareMode = vbTextCompare
    
    Dim ws As Worksheet, lo As ListObject
    Set lo = Nothing
    For Each ws In ThisWorkbook.Worksheets
        On Error Resume Next
        Set lo = ws.ListObjects("DasaTable")
        On Error GoTo 0
        If Not lo Is Nothing Then Exit For
    Next ws
    
    If Not lo Is Nothing Then
        Dim dHdr As Object
        Dim dData As Variant
        Dim iLord As Long, iOrder As Long, iDur As Long
        Dim lordArr(1 To 9) As String, ordArr(1 To 9) As Double
        Dim nPend As Long, R As Long
        Dim dur As String, ord As Double, i As Long, j As Long, tD As Double, tS As String
        
        Set dHdr = MapHeaders(lo.HeaderRowRange)
        iLord = HCol(dHdr, Array("DASALORD", "DasaLord", "PLANET", "Plane"))
        iOrder = HCol(dHdr, Array("DASAORDER", "DasaOrder"))
        iDur = HCol(dHdr, Array("DASA DURATION LEFT", "Dasa Duration Left", "BALANCE", "REMAINING"))
        
        If iLord > 0 And iOrder > 0 And iDur > 0 Then
            dData = lo.DataBodyRange.Value
            For R = 1 To UBound(dData, 1)
                dur = Trim$(CStr(dData(R, iDur)))
                If Len(dur) > 0 And Left$(dur, 1) <> "0" Then
                    ord = Val(dData(R, iOrder))
                    If ord > 0 Then
                        nPend = nPend + 1
                        If nPend <= 9 Then
                            lordArr(nPend) = ProperPlanetName(dData(R, iLord))
                            ordArr(nPend) = ord
                        End If
                    End If
                End If
            Next R
            
            If nPend > 1 Then
                For i = 1 To nPend - 1
                    For j = i + 1 To nPend
                        If ordArr(j) < ordArr(i) Then
                            tD = ordArr(i): ordArr(i) = ordArr(j): ordArr(j) = tD
                            tS = lordArr(i): lordArr(i) = lordArr(j): lordArr(j) = tS
                        End If
                    Next j
                Next i
            End If
            
            Dim useCount As Long
            If mdLimit < 0 Or mdLimit > nPend Then
                useCount = nPend
            Else
                useCount = mdLimit
            End If
            
            For i = 1 To useCount
                If Len(lordArr(i)) > 0 Then allowedMD(lordArr(i)) = True
            Next i
        End If
    End If
    
    Application.ScreenUpdating = False
    Application.EnableEvents = False
    Application.Calculation = xlCalculationManual
    
    Dim rowComb As Long              ' <-- i is already declared above; do NOT redeclare
    Dim lvl As Double
    Dim NLfreq As Double, Totfreq As Double
    Dim wtd As Double, wtdNoSSL As Double
    Dim pSSL As Double, pNoSSL As Double, dSSL As Double
    
    Dim mdLord As String, adLord As String, pdLord As String
    Dim suLord As String, prLord As String, dehLord As String
    
    Dim depth As Long
    Dim passMD As String, passAD As String, passPD As String
    Dim passSU As String, passPR As String, passDEH As String
    
    Dim evStart As Variant, evEnd As Variant, evMid As Variant
    Dim durDays As Variant
    Dim evYear As Long
    
    For rowComb = 2 To lastRow
        
        If outRow - 2 >= maxRows Then Exit For
        
        If Trim$(CStr(wsComb.Cells(rowComb, cMD).Value)) <> "" Then
            
            mdLord = ProperPlanetName(wsComb.Cells(rowComb, cMD).Value)
            adLord = ProperPlanetName(wsComb.Cells(rowComb, cAD).Value)
            pdLord = ProperPlanetName(wsComb.Cells(rowComb, cPD).Value)
            suLord = ProperPlanetName(wsComb.Cells(rowComb, cSU).Value)
            prLord = ProperPlanetName(wsComb.Cells(rowComb, cPR).Value)
            dehLord = ProperPlanetName(wsComb.Cells(rowComb, cDEH).Value)
            
            If allowedMD.count > 0 Then
                If Not allowedMD.Exists(mdLord) Then GoTo NextSeqRow
            End If
            
            If Not IsBhuktiAllowed_FromDasaTable(mdLord, adLord) Then GoTo NextSeqRow
            If Not IsAntraAllowed_FromDasaTable(mdLord, adLord, pdLord) Then GoTo NextSeqRow
            
            pickRow.Cells(1, 1).Value = mdLord
            pickRow.Cells(1, 2).Value = adLord
            pickRow.Cells(1, 3).Value = pdLord
            pickRow.Cells(1, 4).Value = suLord
            pickRow.Cells(1, 5).Value = prLord
            pickRow.Cells(1, 6).Value = dehLord
            
            wsGrid.Range(DATA_BLOCK_ADDR).Calculate
            arrSummary = ConnSummaryCore(wsGrid, DATA_BLOCK_ADDR)
            
            For i = 1 To UBound(arrSummary, 1)
                
                lvl = SafeDbl(arrSummary(i, 7))
                If lvl < minLvl Then GoTo NextPlanet
                
                NLfreq = SafeDbl(arrSummary(i, 9))
                Totfreq = SafeDbl(arrSummary(i, 8))
                wtd = FixTiny(arrSummary(i, 11), True)
                wtdNoSSL = FixTiny(arrSummary(i, 12), True)
                
                pSSL = NLfreq * 2 + Totfreq * 1 + wtd * 0.5 + lvl * 0.25
                pNoSSL = NLfreq * 2 + Totfreq * 1 + wtdNoSSL * 0.5 + lvl * 0.25
                dSSL = pSSL - pNoSSL
                
                If pNoSSL < minProb Then GoTo NextPlanet
                
                depth = CLng(lvl)
                If depth < 1 Then depth = 1
                If depth > 6 Then depth = 6
                
                passMD = "": passAD = "": passPD = ""
                passSU = "": passPR = "": passDEH = ""
                
                If depth >= 1 Then passMD = mdLord
                If depth >= 2 Then passAD = adLord
                If depth >= 3 Then passPD = pdLord
                If depth >= 4 Then passSU = suLord
                If depth >= 5 Then passPR = prLord
                If depth >= 6 Then passDEH = dehLord
                
                evStart = DasaEventDateFromTable(passMD, passAD, passPD, passSU, passPR, passDEH, "START")
                evEnd = DasaEventDateFromTable(passMD, passAD, passPD, passSU, passPR, passDEH, "END")
                evMid = DasaEventDateFromTable(passMD, passAD, passPD, passSU, passPR, passDEH, "MID")
                
                If IsDate(evStart) And IsDate(evEnd) Then
                    durDays = CDbl(evEnd) - CDbl(evStart)
                Else
                    durDays = vbNullString
                End If
                
                If minYear > 0 And IsDate(evStart) Then
                    evYear = Year(CDate(evStart))
                    If evYear < minYear Then GoTo NextPlanet
                End If
                
                wsOut.Cells(outRow, 1).Value = rowComb
                wsOut.Cells(outRow, 2).Value = mdLord
                wsOut.Cells(outRow, 3).Value = adLord
                wsOut.Cells(outRow, 4).Value = pdLord
                wsOut.Cells(outRow, 5).Value = suLord
                wsOut.Cells(outRow, 6).Value = prLord
                wsOut.Cells(outRow, 7).Value = dehLord
                
                wsOut.Cells(outRow, 8).Value = arrSummary(i, 0)
                wsOut.Cells(outRow, 9).Value = FixTiny(lvl)
                wsOut.Cells(outRow, 10).Value = FixTiny(Totfreq)
                wsOut.Cells(outRow, 11).Value = FixTiny(NLfreq)
                wsOut.Cells(outRow, 12).Value = FixTiny(arrSummary(i, 10), True)
                wsOut.Cells(outRow, 13).Value = wtd
                wsOut.Cells(outRow, 14).Value = wtdNoSSL
                wsOut.Cells(outRow, 15).Value = Round(pSSL, 2)
                wsOut.Cells(outRow, 16).Value = Round(pNoSSL, 2)
                wsOut.Cells(outRow, 17).Value = Round(dSSL, 2)
                
                wsOut.Cells(outRow, 19).Value = evStart
                wsOut.Cells(outRow, 20).Value = evEnd
                wsOut.Cells(outRow, 21).Value = evMid
                wsOut.Cells(outRow, 22).Value = durDays
                
                outRow = outRow + 1
                If outRow - 2 >= maxRows Then Exit For
                
NextPlanet:
            Next i
        End If
        
NextSeqRow:
        If outRow - 2 >= maxRows Then Exit For
    Next rowComb
    
    Dim lastDataRow As Long
    lastDataRow = outRow - 1
    
    If lastDataRow >= 2 Then
        With wsOut.Sort
            .SortFields.Clear
            .SortFields.Add key:=wsOut.Range("S2:S" & lastDataRow), _
                SortOn:=xlSortOnValues, order:=xlAscending, DataOption:=xlSortNormal
            .SortFields.Add key:=wsOut.Range("P2:P" & lastDataRow), _
                SortOn:=xlSortOnValues, order:=xlDescending, DataOption:=xlSortNormal
            .SortFields.Add key:=wsOut.Range("Q2:Q" & lastDataRow), _
                SortOn:=xlSortOnValues, order:=xlDescending, DataOption:=xlSortNormal
            .SetRange wsOut.Range("A1:V" & lastDataRow)
            .header = xlYes
            .Apply
        End With
    End If
    
    Dim rank As Long, rowIdx As Long
    rank = 1
    For rowIdx = 2 To lastDataRow
        wsOut.Cells(rowIdx, 18).Value = rank
        rank = rank + 1
    Next rowIdx
    
    wsOut.Columns.AutoFit
    
    Application.ScreenUpdating = True
    Application.EnableEvents = True
    Application.Calculation = xlCalculationAutomatic
End Sub


'=============================
' Duration helper
'=============================
Public Function DurationToText(ByVal durDays As Variant) As String
    On Error GoTo done

    If Not IsNumeric(durDays) Then Exit Function

    Dim D As Double
    D = CDbl(durDays)
    If D <= 0 Then Exit Function

    Dim Days As Long, hours As Long, Minutes As Long
    Dim remD As Double, totalMinutes As Long
    Dim parts As String

    If D >= 1 Then
        Days = Fix(D)
        remD = D - Days
        totalMinutes = CLng(Round(remD * 24# * 60#, 0))
    Else
        Days = 0
        totalMinutes = CLng(Round(D * 24# * 60#, 0))
    End If

    hours = totalMinutes \ 60
    Minutes = totalMinutes Mod 60

    If Days > 0 Then parts = parts & Days & "d "
    If hours > 0 Then parts = parts & hours & "h "
    If Minutes > 0 Then parts = parts & Minutes & "m"

    DurationToText = Trim$(parts)
done:
End Function

'=============================
' DasaTable helpers
'=============================
Private Function GetDasaTable() As ListObject
    Dim ws As Worksheet, lo As ListObject
    For Each ws In ThisWorkbook.Worksheets
        On Error Resume Next
        Set lo = ws.ListObjects("DasaTable")
        On Error GoTo 0
        If Not lo Is Nothing Then
            Set GetDasaTable = lo
            Exit Function
        End If
    Next ws
End Function

Public Function IsBhuktiAllowed_FromDasaTable2( _
    ByVal mdLord As String, _
    ByVal adLord As String) As Boolean

    Dim lo As ListObject
    Set lo = GetDasaTable()
    If lo Is Nothing Then Exit Function

    Dim hdr As Object
    Set hdr = MapHeaders(lo.HeaderRowRange)

    Dim iLord As Long, iBhSel As Long
    iLord = HCol(hdr, Array("DASALORD", "DasaLord", "PLANET", "Plane"))
    iBhSel = HCol(hdr, Array("BHUKTISELECTION", "BhuktiSelection"))

    If iLord = 0 Or iBhSel = 0 Then Exit Function

    Dim Data As Variant
    Data = lo.DataBodyRange.Value

    Dim R As Long, lord As String, sel As String
    Dim wantAD As String
    wantAD = UCase$(ProperPlanetName(adLord))

    For R = 1 To UBound(Data, 1)
        lord = UCase$(ProperPlanetName(Data(R, iLord)))
        If lord = UCase$(ProperPlanetName(mdLord)) Then
            sel = CStr(Data(R, iBhSel))
            If Len(Trim$(sel)) = 0 Then Exit Function

            Dim s As String, parts As Variant, i As Long, token As String
            s = UCase$(sel)
            s = Replace(s, ";", ",")
            s = Replace(s, " ", "")
            Do While InStr(s, ",,") > 0
                s = Replace(s, ",,", ",")
            Loop
            If Left$(s, 1) = "," Then s = mid$(s, 2)
            If Right$(s, 1) = "," Then s = Left$(s, Len(s) - 1)

            parts = Split(s, ",")
            For i = LBound(parts) To UBound(parts)
                token = Trim$(parts(i))
                If token = wantAD Then
                    IsBhuktiAllowed_FromDasaTable2 = True
                    Exit Function
                End If
            Next i

            Exit Function
        End If
    Next R
End Function

Public Function IsAntraAllowed_FromDasaTable2( _
    ByVal mdLord As String, _
    ByVal adLord As String, _
    ByVal pdLord As String) As Boolean

    Dim lo As ListObject
    Set lo = GetDasaTable()
    If lo Is Nothing Then Exit Function

    Dim hdr As Object
    Set hdr = MapHeaders(lo.HeaderRowRange)

    Dim iLord As Long, iAnSel As Long
    iLord = HCol(hdr, Array("DASALORD", "DasaLord", "PLANET", "Plane"))
    iAnSel = HCol(hdr, Array("ANTRASELECTION", "AntraSelection"))

    If iLord = 0 Or iAnSel = 0 Then Exit Function

    Dim Data As Variant
    Data = lo.DataBodyRange.Value

    Dim R As Long, lord As String, sel As String
    Dim wantAD As String, wantPD As String
    Dim s As String, key As String, pos As Long, colonPos As Long, nextBar As Long
    Dim block As String, parts As Variant, i As Long, token As String

    wantAD = UCase$(ProperPlanetName(adLord))
    wantPD = UCase$(ProperPlanetName(pdLord))

    For R = 1 To UBound(Data, 1)
        lord = UCase$(ProperPlanetName(Data(R, iLord)))
        If lord = UCase$(ProperPlanetName(mdLord)) Then
            sel = CStr(Data(R, iAnSel))
            If Len(Trim$(sel)) = 0 Then Exit Function

            s = UCase$(sel)
            key = "ANTRAOFBL(" & wantAD & "):"
            pos = InStr(s, key)
            If pos = 0 Then Exit Function

            colonPos = pos + Len(key) - 1
            nextBar = InStr(colonPos + 1, s, "|")
            If nextBar = 0 Then
                block = mid$(s, colonPos + 1)
            Else
                block = mid$(s, colonPos + 1, nextBar - colonPos - 1)
            End If

            block = Replace(block, ";", ",")
            block = Replace(block, " ", "")
            Do While InStr(block, ",,") > 0
                block = Replace(block, ",,", ",")
            Loop
            If Left$(block, 1) = "," Then block = mid$(block, 2)
            If Right$(block, 1) = "," Then block = Left$(block, Len(block) - 1)

            parts = Split(block, ",")
            For i = LBound(parts) To UBound(parts)
                token = Trim$(parts(i))
                If token = wantPD Then
                    IsAntraAllowed_FromDasaTable2 = True
                    Exit Function
                End If
            Next i

            Exit Function
        End If
    Next R
End Function

'=============================
' Main analysis macro
'=============================
Public Sub BatchAnalyze_MD_Combinations_Full3()
    Const GRID_SHEET_NAME As String = "CIL"
    Const COMB_SHEET_NAME As String = "MD_Combinations_Full"
    Const OUT_SHEET_NAME  As String = "MD_Combo_Analysis"
    Const PICK_ADDR       As String = "GG20:GL20"

    Dim wsGrid As Worksheet, wsComb As Worksheet, wsOut As Worksheet
    Dim cMD As Long, cAD As Long, cPD As Long, cSU As Long, cPR As Long, cDEH As Long

    Set wsGrid = ThisWorkbook.Worksheets(GRID_SHEET_NAME)
    Set wsComb = ThisWorkbook.Worksheets(COMB_SHEET_NAME)

    On Error Resume Next
    Set wsOut = ThisWorkbook.Worksheets(OUT_SHEET_NAME)
    On Error GoTo 0
    If wsOut Is Nothing Then
        Set wsOut = ThisWorkbook.Worksheets.Add(After:=wsComb)
        wsOut.name = OUT_SHEET_NAME
    Else
        wsOut.Cells.ClearContents
    End If

    Dim hdr As Object
    Set hdr = MapHeaders(wsComb.rows(1))

    cMD = HCol(hdr, Array("MD"))
    cAD = HCol(hdr, Array("AD"))
    cPD = HCol(hdr, Array("PD"))
    cSU = HCol(hdr, Array("SU"))
    cPR = HCol(hdr, Array("PRANA", "PR"))
    cDEH = HCol(hdr, Array("DEH"))

    If cMD = 0 Or cAD = 0 Or cPD = 0 Or cSU = 0 Or cPR = 0 Or cDEH = 0 Then
        MsgBox "MD_Combinations_Full is missing MD/AD/PD/SU/PRANA/DEH.", vbCritical
        Exit Sub
    End If

    wsOut.Range("A1").Resize(1, 23).Value = Array( _
        "SeqRow", "MD", "AD", "PD", "SU", "PRANA", "DEH", _
        "Planet", "LevelsConnected", "Freq_Total", "Freq_NLType", _
        "Score", "WTDSCORE", "WTDSCORE_NOSSL", _
        "ProbScore_SSL", "ProbScore_NoSSL", "Delta_SSL", "Rank", _
        "EventStart", "EventEnd", "EventDate", _
        "EventDurationDays", "EventDurationText")

    Dim lastRow As Long
    lastRow = wsComb.Cells(wsComb.rows.count, cMD).End(xlUp).row

    Dim pickRow As Range
    Set pickRow = wsGrid.Range(PICK_ADDR)

    Dim arrSummary As Variant
    Dim outRow As Long
    outRow = 2

    Dim minLvl As Long, minProb As Double, minYear As Long, maxRows As Long, mdLimit As Long
    minLvl = CLng(Val(wsGrid.Range("GL10").Value))
    If minLvl <= 0 Then minLvl = 3
    minProb = CDbl(Val(wsGrid.Range("GL11").Value))
    minYear = CLng(Val(wsGrid.Range("GL12").Value))
    maxRows = CLng(Val(wsGrid.Range("GL13").Value))
    If maxRows <= 0 Then maxRows = 1000000
    mdLimit = CLng(Val(wsGrid.Range("GL14").Value))  ' -1 = all pending

    Dim allowedMD As Object
    Set allowedMD = CreateObject("Scripting.Dictionary")
    allowedMD.CompareMode = vbTextCompare

    Dim loDasa As ListObject
    Set loDasa = GetDasaTable()

    If Not loDasa Is Nothing Then
        Dim dHdr As Object
        Dim dData As Variant
        Dim iLord As Long, iOrder As Long, iDur As Long
        Dim lordArr(1 To 9) As String, ordArr(1 To 9) As Double
        Dim nPend As Long, R As Long
        Dim dur As String, ord As Double, i As Long, j As Long
        Dim tD As Double, tS As String

        Set dHdr = MapHeaders(loDasa.HeaderRowRange)
        iLord = HCol(dHdr, Array("DASALORD", "DasaLord", "PLANET", "Plane"))
        iOrder = HCol(dHdr, Array("DASAORDER", "DasaOrder"))
        iDur = HCol(dHdr, Array("DASA DURATION LEFT", "Dasa Duration Left", "BALANCE", "REMAINING"))

        If iLord > 0 And iOrder > 0 And iDur > 0 Then
            dData = loDasa.DataBodyRange.Value
            For R = 1 To UBound(dData, 1)
                dur = Trim$(CStr(dData(R, iDur)))
                If Len(dur) > 0 And Left$(dur, 1) <> "0" Then
                    ord = Val(dData(R, iOrder))
                    If ord > 0 Then
                        nPend = nPend + 1
                        If nPend <= 9 Then
                            lordArr(nPend) = ProperPlanetName(dData(R, iLord))
                            ordArr(nPend) = ord
                        End If
                    End If
                End If
            Next R

            If nPend > 1 Then
                For i = 1 To nPend - 1
                    For j = i + 1 To nPend
                        If ordArr(j) < ordArr(i) Then
                            tD = ordArr(i): ordArr(i) = ordArr(j): ordArr(j) = tD
                            tS = lordArr(i): lordArr(i) = lordArr(j): lordArr(j) = tS
                        End If
                    Next j
                Next i
            End If

            Dim useCount As Long
            If mdLimit < 0 Or mdLimit > nPend Then
                useCount = nPend
            Else
                useCount = mdLimit
            End If

            For i = 1 To useCount
                If Len(lordArr(i)) > 0 Then allowedMD(lordArr(i)) = True
            Next i
        End If
    End If

    Application.ScreenUpdating = False
    Application.EnableEvents = False
    Application.Calculation = xlCalculationManual

    Dim rowComb As Long
    Dim lvl As Double
    Dim NLfreq As Double, Totfreq As Double
    Dim wtd As Double, wtdNoSSL As Double
    Dim pSSL As Double, pNoSSL As Double, dSSL As Double

    Dim mdLord As String, adLord As String, pdLord As String
    Dim suLord As String, prLord As String, dehLord As String

    Dim depth As Long
    Dim passMD As String, passAD As String, passPD As String
    Dim passSU As String, passPR As String, passDEH As String

    Dim evStart As Variant, evEnd As Variant, evMid As Variant
    Dim durDays As Variant, durText As String
    Dim evYear As Long
    Dim iPlanet As Long

    For rowComb = 2 To lastRow

        If outRow - 2 >= maxRows Then Exit For

        If Trim$(CStr(wsComb.Cells(rowComb, cMD).Value)) <> "" Then

            mdLord = ProperPlanetName(wsComb.Cells(rowComb, cMD).Value)
            adLord = ProperPlanetName(wsComb.Cells(rowComb, cAD).Value)
            pdLord = ProperPlanetName(wsComb.Cells(rowComb, cPD).Value)
            suLord = ProperPlanetName(wsComb.Cells(rowComb, cSU).Value)
            prLord = ProperPlanetName(wsComb.Cells(rowComb, cPR).Value)
            dehLord = ProperPlanetName(wsComb.Cells(rowComb, cDEH).Value)

            If allowedMD.count > 0 Then
                If Not allowedMD.Exists(mdLord) Then GoTo NextSeqRow
            End If

            If Not IsBhuktiAllowed_FromDasaTable(mdLord, adLord) Then GoTo NextSeqRow
            If Not IsAntraAllowed_FromDasaTable(mdLord, adLord, pdLord) Then GoTo NextSeqRow

            pickRow.Cells(1, 1).Value = mdLord
            pickRow.Cells(1, 2).Value = adLord
            pickRow.Cells(1, 3).Value = pdLord
            pickRow.Cells(1, 4).Value = suLord
            pickRow.Cells(1, 5).Value = prLord
            pickRow.Cells(1, 6).Value = dehLord

            wsGrid.Range(DATA_BLOCK_ADDR).Calculate
            arrSummary = ConnSummaryCore(wsGrid, DATA_BLOCK_ADDR)

            For iPlanet = 1 To UBound(arrSummary, 1)

                lvl = SafeDbl(arrSummary(iPlanet, 7))
                If lvl < minLvl Then GoTo NextPlanet

                NLfreq = SafeDbl(arrSummary(iPlanet, 9))
                Totfreq = SafeDbl(arrSummary(iPlanet, 8))
                wtd = FixTiny(arrSummary(iPlanet, 11), True)
                wtdNoSSL = FixTiny(arrSummary(iPlanet, 12), True)

                If wtd < 0 Or wtdNoSSL < 0 Then GoTo NextPlanet

                pSSL = NLfreq * 2 + Totfreq * 1 + wtd * 0.5 + lvl * 0.25
                pNoSSL = NLfreq * 2 + Totfreq * 1 + wtdNoSSL * 0.5 + lvl * 0.25
                dSSL = pSSL - pNoSSL

                If pNoSSL < minProb Then GoTo NextPlanet

                depth = CLng(lvl)
                If depth < 1 Then depth = 1
                If depth > 6 Then depth = 6

                passMD = "": passAD = "": passPD = ""
                passSU = "": passPR = "": passDEH = ""

                If depth >= 1 Then passMD = mdLord
                If depth >= 2 Then passAD = adLord
                If depth >= 3 Then passPD = pdLord
                If depth >= 4 Then passSU = suLord
                If depth >= 5 Then passPR = prLord
                If depth >= 6 Then passDEH = dehLord

                evStart = DasaEventDateFromTable(passMD, passAD, passPD, passSU, passPR, passDEH, "START")
                evEnd = DasaEventDateFromTable(passMD, passAD, passPD, passSU, passPR, passDEH, "END")
                evMid = DasaEventDateFromTable(passMD, passAD, passPD, passSU, passPR, passDEH, "MID")

                If IsDate(evStart) And IsDate(evEnd) Then
                    durDays = CDbl(evEnd) - CDbl(evStart)
                Else
                    durDays = vbNullString
                End If

                If IsNumeric(durDays) And durDays > 0 Then
                    durText = DurationToText(durDays)
                Else
                    durText = vbNullString
                End If

                If minYear > 0 And IsDate(evStart) Then
                    evYear = Year(CDate(evStart))
                    If evYear < minYear Then GoTo NextPlanet
                End If

                wsOut.Cells(outRow, 1).Value = rowComb
                wsOut.Cells(outRow, 2).Value = mdLord
                wsOut.Cells(outRow, 3).Value = adLord
                wsOut.Cells(outRow, 4).Value = pdLord
                wsOut.Cells(outRow, 5).Value = suLord
                wsOut.Cells(outRow, 6).Value = prLord
                wsOut.Cells(outRow, 7).Value = dehLord

                wsOut.Cells(outRow, 8).Value = arrSummary(iPlanet, 0)
                wsOut.Cells(outRow, 9).Value = FixTiny(lvl)
                wsOut.Cells(outRow, 10).Value = FixTiny(Totfreq)
                wsOut.Cells(outRow, 11).Value = FixTiny(NLfreq)
                wsOut.Cells(outRow, 12).Value = FixTiny(arrSummary(iPlanet, 10), True)
                wsOut.Cells(outRow, 13).Value = wtd
                wsOut.Cells(outRow, 14).Value = wtdNoSSL
                wsOut.Cells(outRow, 15).Value = Round(pSSL, 2)
                wsOut.Cells(outRow, 16).Value = Round(pNoSSL, 2)
                wsOut.Cells(outRow, 17).Value = Round(dSSL, 2)

                wsOut.Cells(outRow, 19).Value = evStart
                wsOut.Cells(outRow, 20).Value = evEnd
                wsOut.Cells(outRow, 21).Value = evMid
                wsOut.Cells(outRow, 22).Value = durDays
                wsOut.Cells(outRow, 23).Value = durText

                outRow = outRow + 1
                If outRow - 2 >= maxRows Then Exit For

NextPlanet:
            Next iPlanet
        End If

NextSeqRow:
        If outRow - 2 >= maxRows Then Exit For
    Next rowComb

    Dim lastDataRow As Long
    lastDataRow = outRow - 1

    If lastDataRow >= 2 Then
        With wsOut.Sort
            .SortFields.Clear
            .SortFields.Add key:=wsOut.Range("S2:S" & lastDataRow), _
                SortOn:=xlSortOnValues, order:=xlAscending, DataOption:=xlSortNormal
            .SortFields.Add key:=wsOut.Range("P2:P" & lastDataRow), _
                SortOn:=xlSortOnValues, order:=xlDescending, DataOption:=xlSortNormal
            .SortFields.Add key:=wsOut.Range("Q2:Q" & lastDataRow), _
                SortOn:=xlSortOnValues, order:=xlDescending, DataOption:=xlSortNormal
            .SetRange wsOut.Range("A1:W" & lastDataRow)
            .header = xlYes
            .Apply
        End With
    End If

    Dim rank As Long, rowIdx As Long
    rank = 1
    For rowIdx = 2 To lastDataRow
        wsOut.Cells(rowIdx, 18).Value = rank
        rank = rank + 1
    Next rowIdx

    wsOut.Columns.AutoFit
    wsOut.Columns(22).NumberFormat = "0.00"

    Application.ScreenUpdating = True
    Application.EnableEvents = True
    Application.Calculation = xlCalculationAutomatic
End Sub

Public Sub BatchAnalyze_MD_Combinations_Full()
    Const GRID_SHEET_NAME As String = "CIL"
    Const COMB_SHEET_NAME As String = "MD_Combinations_Full"
    Const OUT_SHEET_NAME  As String = "MD_Combo_Analysis"
    Const PICK_ADDR       As String = "GG20:GL20"

    Dim wsGrid As Worksheet, wsComb As Worksheet, wsOut As Worksheet
    Dim cMD As Long, cAD As Long, cPD As Long, cSU As Long, cPR As Long, cDEH As Long

    Set wsGrid = ThisWorkbook.Worksheets(GRID_SHEET_NAME)
    Set wsComb = ThisWorkbook.Worksheets(COMB_SHEET_NAME)

    On Error Resume Next
    Set wsOut = ThisWorkbook.Worksheets(OUT_SHEET_NAME)
    On Error GoTo 0
    If wsOut Is Nothing Then
        Set wsOut = ThisWorkbook.Worksheets.Add(After:=wsComb)
        wsOut.name = OUT_SHEET_NAME
    Else
        wsOut.Cells.ClearContents
    End If

    Dim hdr As Object
    Set hdr = MapHeaders(wsComb.rows(1))

    cMD = HCol(hdr, Array("MD"))
    cAD = HCol(hdr, Array("AD"))
    cPD = HCol(hdr, Array("PD"))
    cSU = HCol(hdr, Array("SU"))
    cPR = HCol(hdr, Array("PRANA", "PR"))
    cDEH = HCol(hdr, Array("DEH"))

    If cMD = 0 Or cAD = 0 Or cPD = 0 Or cSU = 0 Or cPR = 0 Or cDEH = 0 Then
        MsgBox "MD_Combinations_Full is missing MD/AD/PD/SU/PRANA/DEH.", vbCritical
        Exit Sub
    End If

    wsOut.Range("A1").Resize(1, 22).Value = Array( _
        "SeqRow", "MD", "AD", "PD", "SU", "PRANA", "DEH", _
        "Planet", "LevelsConnected", "Freq_Total", "Freq_NLType", _
        "Score", "WTDSCORE", "WTDSCORE_NOSSL", _
        "ProbScore_SSL", "ProbScore_NoSSL", "Delta_SSL", "Rank", _
        "EventStart", "EventEnd", "EventDate", "EventDurationDays")

    Dim lastRow As Long
    lastRow = wsComb.Cells(wsComb.rows.count, cMD).End(xlUp).row

    Dim pickRow As Range
    Set pickRow = wsGrid.Range(PICK_ADDR)

    Dim arrSummary As Variant
    Dim outRow As Long
    outRow = 2

    Dim minLvl As Long, minProb As Double, minYear As Long, maxRows As Long, mdLimit As Long
    minLvl = CLng(Val(wsGrid.Range("GL10").Value))
    If minLvl <= 0 Then minLvl = 3

    minProb = CDbl(Val(wsGrid.Range("GL11").Value))
    minYear = CLng(Val(wsGrid.Range("GL12").Value))

    maxRows = CLng(Val(wsGrid.Range("GL13").Value))
    If maxRows <= 0 Then maxRows = 1000000

    mdLimit = CLng(Val(wsGrid.Range("GL14").Value))

    Dim allowedMD As Object
    Set allowedMD = CreateObject("Scripting.Dictionary")
    allowedMD.CompareMode = vbTextCompare

    Dim ws As Worksheet, lo As ListObject
    Set lo = Nothing
    For Each ws In ThisWorkbook.Worksheets
        On Error Resume Next
        Set lo = ws.ListObjects("DasaTable")
        On Error GoTo 0
        If Not lo Is Nothing Then Exit For
    Next ws

    If Not lo Is Nothing Then
        Dim dHdr As Object
        Dim dData As Variant
        Dim iLord As Long, iOrder As Long, iDur As Long
        Dim lordArr(1 To 9) As String, ordArr(1 To 9) As Double
        Dim nPend As Long, R As Long
        Dim dur As String, ord As Double
        Dim i As Long, j As Long
        Dim tD As Double, tS As String

        Set dHdr = MapHeaders(lo.HeaderRowRange)
        iLord = HCol(dHdr, Array("DASALORD", "DasaLord", "PLANET", "Plane"))
        iOrder = HCol(dHdr, Array("DASAORDER", "DasaOrder"))
        iDur = HCol(dHdr, Array("DASA DURATION LEFT", "Dasa Duration Left", "BALANCE", "REMAINING"))

        If iLord > 0 And iOrder > 0 And iDur > 0 Then
            dData = lo.DataBodyRange.Value
            For R = 1 To UBound(dData, 1)
                dur = Trim$(CStr(dData(R, iDur)))
                If Len(dur) > 0 And Left$(dur, 1) <> "0" Then
                    ord = Val(dData(R, iOrder))
                    If ord > 0 Then
                        nPend = nPend + 1
                        If nPend <= 9 Then
                            lordArr(nPend) = ProperPlanetName(dData(R, iLord))
                            ordArr(nPend) = ord
                        End If
                    End If
                End If
            Next R

            If nPend > 1 Then
                For i = 1 To nPend - 1
                    For j = i + 1 To nPend
                        If ordArr(j) < ordArr(i) Then
                            tD = ordArr(i): ordArr(i) = ordArr(j): ordArr(j) = tD
                            tS = lordArr(i): lordArr(i) = lordArr(j): lordArr(j) = tS
                        End If
                    Next j
                Next i
            End If

            Dim useCount As Long
            If mdLimit < 0 Or mdLimit > nPend Then
                useCount = nPend
            Else
                useCount = mdLimit
            End If

            For i = 1 To useCount
                If Len(lordArr(i)) > 0 Then allowedMD(lordArr(i)) = True
            Next i
        End If
    End If

    Application.ScreenUpdating = False
    Application.EnableEvents = False
    Application.Calculation = xlCalculationManual

    Dim rowComb As Long
    Dim lvl As Double
    Dim NLfreq As Double, Totfreq As Double
    Dim wtd As Double, wtdNoSSL As Double
    Dim pSSL As Double, pNoSSL As Double, dSSL As Double

    Dim mdLord As String, adLord As String, pdLord As String
    Dim suLord As String, prLord As String, dehLord As String

    Dim depth As Long
    Dim passMD As String, passAD As String, passPD As String
    Dim passSU As String, passPR As String, passDEH As String

    Dim evStart As Variant, evEnd As Variant, evMid As Variant
    Dim durDays As Variant
    Dim evYear As Long

    For rowComb = 2 To lastRow

        If outRow - 2 >= maxRows Then Exit For

        If Trim$(CStr(wsComb.Cells(rowComb, cMD).Value)) <> "" Then

            mdLord = ProperPlanetName(wsComb.Cells(rowComb, cMD).Value)
            adLord = ProperPlanetName(wsComb.Cells(rowComb, cAD).Value)
            pdLord = ProperPlanetName(wsComb.Cells(rowComb, cPD).Value)
            suLord = ProperPlanetName(wsComb.Cells(rowComb, cSU).Value)
            prLord = ProperPlanetName(wsComb.Cells(rowComb, cPR).Value)
            dehLord = ProperPlanetName(wsComb.Cells(rowComb, cDEH).Value)

            If allowedMD.count > 0 Then
                If Not allowedMD.Exists(mdLord) Then GoTo NextSeqRow
            End If

            If Not IsBhuktiAllowed_FromDasaTable(mdLord, adLord) Then GoTo NextSeqRow
            If Not IsAntraAllowed_FromDasaTable(mdLord, adLord, pdLord) Then GoTo NextSeqRow

            pickRow.Cells(1, 1).Value = mdLord
            pickRow.Cells(1, 2).Value = adLord
            pickRow.Cells(1, 3).Value = pdLord
            pickRow.Cells(1, 4).Value = suLord
            pickRow.Cells(1, 5).Value = prLord
            pickRow.Cells(1, 6).Value = dehLord

            wsGrid.Range(DATA_BLOCK_ADDR).Calculate
            arrSummary = ConnSummaryCore(wsGrid, DATA_BLOCK_ADDR)

            For i = 1 To UBound(arrSummary, 1)

                lvl = SafeDbl(arrSummary(i, 7))
                If lvl < minLvl Then GoTo NextPlanet

                NLfreq = SafeDbl(arrSummary(i, 9))
                Totfreq = SafeDbl(arrSummary(i, 8))
                wtd = FixTiny(arrSummary(i, 11), True)
                wtdNoSSL = FixTiny(arrSummary(i, 12), True)

                If (wtd <= 0 And wtdNoSSL <= 0) Then GoTo NextPlanet

                pSSL = NLfreq * 2 + Totfreq * 1 + wtd * 0.5 + lvl * 0.25
                pNoSSL = NLfreq * 2 + Totfreq * 1 + wtdNoSSL * 0.5 + lvl * 0.25
                dSSL = pSSL - pNoSSL

                If pNoSSL < minProb Then GoTo NextPlanet

                depth = CLng(lvl)
                If depth < 1 Then depth = 1
                If depth > 6 Then depth = 6

                passMD = "": passAD = "": passPD = ""
                passSU = "": passPR = "": passDEH = ""

                If depth >= 1 Then passMD = mdLord
                If depth >= 2 Then passAD = adLord
                If depth >= 3 Then passPD = pdLord
                If depth >= 4 Then passSU = suLord
                If depth >= 5 Then passPR = prLord
                If depth >= 6 Then passDEH = dehLord

                evStart = DasaEventDateFromTable(passMD, passAD, passPD, passSU, passPR, passDEH, "START")
                evEnd = DasaEventDateFromTable(passMD, passAD, passPD, passSU, passPR, passDEH, "END")
                evMid = DasaEventDateFromTable(passMD, passAD, passPD, passSU, passPR, passDEH, "MID")

                If IsDate(evStart) And IsDate(evEnd) Then
                    durDays = CDbl(evEnd) - CDbl(evStart)
                Else
                    durDays = vbNullString
                End If

                If minYear > 0 And IsDate(evStart) Then
                    evYear = Year(CDate(evStart))
                    If evYear < minYear Then GoTo NextPlanet
                End If

                wsOut.Cells(outRow, 1).Value = rowComb
                wsOut.Cells(outRow, 2).Value = mdLord
                wsOut.Cells(outRow, 3).Value = adLord
                wsOut.Cells(outRow, 4).Value = pdLord
                wsOut.Cells(outRow, 5).Value = suLord
                wsOut.Cells(outRow, 6).Value = prLord
                wsOut.Cells(outRow, 7).Value = dehLord

                wsOut.Cells(outRow, 8).Value = arrSummary(i, 0)
                wsOut.Cells(outRow, 9).Value = FixTiny(lvl)
                wsOut.Cells(outRow, 10).Value = FixTiny(Totfreq)
                wsOut.Cells(outRow, 11).Value = FixTiny(NLfreq)
                wsOut.Cells(outRow, 12).Value = FixTiny(arrSummary(i, 10), True)
                wsOut.Cells(outRow, 13).Value = wtd
                wsOut.Cells(outRow, 14).Value = wtdNoSSL
                wsOut.Cells(outRow, 15).Value = Round(pSSL, 2)
                wsOut.Cells(outRow, 16).Value = Round(pNoSSL, 2)
                wsOut.Cells(outRow, 17).Value = Round(dSSL, 2)

                wsOut.Cells(outRow, 19).Value = evStart
                wsOut.Cells(outRow, 20).Value = evEnd
                wsOut.Cells(outRow, 21).Value = evMid
                wsOut.Cells(outRow, 22).Value = durDays

                outRow = outRow + 1
                If outRow - 2 >= maxRows Then Exit For

NextPlanet:
            Next i
        End If

NextSeqRow:
        If outRow - 2 >= maxRows Then Exit For
    Next rowComb

    Dim lastDataRow As Long
    lastDataRow = outRow - 1

    If lastDataRow >= 2 Then
        Dim rowIdx As Long
        Dim rank As Long

        For rowIdx = 2 To lastDataRow
            wsOut.Cells(rowIdx, 18).Value = rowIdx - 1
        Next rowIdx

        With wsOut.Sort
            .SortFields.Clear

            .SortFields.Add _
                key:=wsOut.Range("N2:N" & lastDataRow), _
                SortOn:=xlSortOnValues, _
                order:=xlDescending, _
                DataOption:=xlSortNormal

            .SortFields.Add _
                key:=wsOut.Range("K2:K" & lastDataRow), _
                SortOn:=xlSortOnValues, _
                order:=xlDescending, _
                DataOption:=xlSortNormal

            .SortFields.Add _
                key:=wsOut.Range("I2:I" & lastDataRow), _
                SortOn:=xlSortOnValues, _
                order:=xlDescending, _
                DataOption:=xlSortNormal

            .SortFields.Add _
                key:=wsOut.Range("L2:L" & lastDataRow), _
                SortOn:=xlSortOnValues, _
                order:=xlDescending, _
                DataOption:=xlSortNormal

            .SortFields.Add _
                key:=wsOut.Range("S2:S" & lastDataRow), _
                SortOn:=xlSortOnValues, _
                order:=xlAscending, _
                DataOption:=xlSortNormal

            .SortFields.Add _
                key:=wsOut.Range("R2:R" & lastDataRow), _
                SortOn:=xlSortOnValues, _
                order:=xlAscending, _
                DataOption:=xlSortNormal

            .SetRange wsOut.Range("A1:V" & lastDataRow)
            .header = xlYes
            .Apply
        End With

        rank = 1
        For rowIdx = 2 To lastDataRow
            wsOut.Cells(rowIdx, 18).Value = rank
            rank = rank + 1
        Next rowIdx

        Dim col As Long
        Dim rngCol As Range
        Dim cs As Object
        Dim cs2 As Object

        ' I to P: separate 3-color scale per column
        For col = 9 To 16   ' I=9, J=10, ... P=16
            Set rngCol = wsOut.Range(wsOut.Cells(2, col), wsOut.Cells(lastDataRow, col))
            rngCol.FormatConditions.Delete
            Set cs = rngCol.FormatConditions.AddColorScale(ColorScaleType:=3)

            With cs.ColorScaleCriteria(1)
                .Type = xlConditionValueLowestValue
                .FormatColor.Color = RGB(0, 176, 80)      ' lowest = green
            End With
            With cs.ColorScaleCriteria(2)
                .Type = xlConditionValuePercentile
                .Value = 50
                .FormatColor.Color = RGB(255, 255, 0)     ' mid = yellow
            End With
            With cs.ColorScaleCriteria(3)
                .Type = xlConditionValueHighestValue
                .FormatColor.Color = RGB(255, 0, 0)       ' highest = red
            End With
        Next col

        ' V column: its own 3-color scale
        Set rngCol = wsOut.Range("V2:V" & lastDataRow)
        rngCol.FormatConditions.Delete
        Set cs2 = rngCol.FormatConditions.AddColorScale(ColorScaleType:=3)

        With cs2.ColorScaleCriteria(1)
            .Type = xlConditionValueLowestValue
            .FormatColor.Color = RGB(0, 176, 80)
        End With
        With cs2.ColorScaleCriteria(2)
            .Type = xlConditionValuePercentile
            .Value = 50
            .FormatColor.Color = RGB(255, 255, 0)
        End With
        With cs2.ColorScaleCriteria(3)
            .Type = xlConditionValueHighestValue
            .FormatColor.Color = RGB(255, 0, 0)
        End With
    End If

    wsOut.Columns.AutoFit

    Application.ScreenUpdating = True
    Application.EnableEvents = True
    Application.Calculation = xlCalculationAutomatic
End Sub


Sub Test_Grid_Speed()
    Dim t As Double
    t = Timer
    
    Dim i As Long
    For i = 1 To 100
        Range("GG20:GL20").Calculate
    Next i
    
    MsgBox "100 recalcs = " & (Timer - t) & " seconds"
End Sub






