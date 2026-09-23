Option Explicit

'=========================================================
'   GLOBAL CACHE : VimDasaTbl
'=========================================================
Public VimDasaArr As Variant
Public VimDasaRowCount As Long
Public VimDasaCol As Object
Public VimDasaLoaded As Boolean

'---------------------------------------------------------
'  INITIALIZER (MUST BE RUN ONCE VIA MACRO)
'---------------------------------------------------------
Public Sub InitConnSummary()
    LoadVimDasaCache
End Sub

Public Sub LoadVimDasaCache()
    Dim lo As ListObject
    Dim lc As ListColumn
    Dim ws As Worksheet

    If VimDasaLoaded Then Exit Sub

    ' ?? CHANGE SHEET NAME IF NEEDED
    Set ws = ThisWorkbook.Worksheets("get")
    Set lo = ws.ListObjects("VimDasaTbl")

    If lo Is Nothing Then
        Err.Raise 5, , "VimDasaTbl not found on sheet DasaCalc"
    End If

    VimDasaArr = lo.DataBodyRange.Value
    VimDasaRowCount = UBound(VimDasaArr, 1)

    Set VimDasaCol = CreateObject("Scripting.Dictionary")
    VimDasaCol.CompareMode = vbTextCompare

    For Each lc In lo.ListColumns
        VimDasaCol(lc.name) = lc.Index
    Next lc

    VimDasaLoaded = True
End Sub

'=========================================================
'   PURE ARRAY WINDOW FINDER (UDF SAFE)
'=========================================================
Public Function GetDasaWindowCachedFromRange( _
    ByVal LevelsConnected As Long, _
    ByVal MD As String, _
    ByVal AD As String, _
    ByVal PD As String, _
    ByVal SU As String, _
    ByVal PRANA As String, _
    ByVal DEH As String _
) As Variant

    Dim r As Long
    Dim rStart As Long, rEnd As Long
    Dim useMD As Boolean, useAD As Boolean, usePD As Boolean
    Dim useSU As Boolean, usePR As Boolean, useDEH As Boolean

    If Not VimDasaLoaded Then
        GetDasaWindowCachedFromRange = Array(0, 0, "", "", 0#, 0#, 0#)
        Exit Function
    End If

    useMD = LevelsConnected >= 1
    useAD = LevelsConnected >= 2
    usePD = LevelsConnected >= 3
    useSU = LevelsConnected >= 4
    usePR = LevelsConnected >= 5
    useDEH = LevelsConnected >= 6

    rStart = 0: rEnd = 0

    For r = 1 To VimDasaRowCount
        If (Not useMD Or VimDasaArr(r, VimDasaCol("MD")) = MD) _
        And (Not useAD Or VimDasaArr(r, VimDasaCol("AD")) = AD) _
        And (Not usePD Or VimDasaArr(r, VimDasaCol("PD")) = PD) _
        And (Not useSU Or VimDasaArr(r, VimDasaCol("SU")) = SU) _
        And (Not usePR Or VimDasaArr(r, VimDasaCol("PRANA")) = PRANA) _
        And (Not useDEH Or VimDasaArr(r, VimDasaCol("DEH")) = DEH) Then

            If rStart = 0 Then rStart = r
            rEnd = r
        End If
    Next r

    If rStart = 0 Then
        GetDasaWindowCachedFromRange = Array(0, 0, "", "", 0#, 0#, 0#)
        Exit Function
    End If

    Dim dStart As Date, dEnd As Date
    Dim durDays As Double

    dStart = VimDasaArr(rStart, VimDasaCol("DasaDate"))

    If rEnd < VimDasaRowCount Then
        dEnd = VimDasaArr(rEnd + 1, VimDasaCol("DasaDate"))
    Else
        dEnd = dStart
    End If

    durDays = dEnd - dStart

    GetDasaWindowCachedFromRange = Array( _
        rStart, _
        rEnd, _
        dStart, _
        dEnd, _
        durDays, _
        durDays / 365.2425, _
        durDays / 30.436875 _
    )
End Function

'=========================================================
'   CORE SUMMARY ENGINE (ARRAY ONLY)
'=========================================================
Private Function ConnSummaryCore( _
    ByVal dataArr As Variant, _
    ByVal MD As String, _
    ByVal AD As String, _
    ByVal PD As String, _
    ByVal SU As String, _
    ByVal PRANA As String, _
    ByVal DEH As String _
) As Variant

    Dim planets As Variant
    planets = Array("Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke")

    Dim p As Long, lc As Long
    Dim raw() As Variant
    ReDim raw(0 To 8, 0 To 19)

    For p = 0 To 8
        lc = 6 ' <<< example connectivity value, replace with your real calc

        raw(p, 0) = planets(p)
        raw(p, 7) = lc

        Dim win As Variant
        win = GetDasaWindowCachedFromRange( _
                lc, MD, AD, PD, SU, PRANA, DEH _
        )

        raw(p, 13) = win(0)
        raw(p, 14) = win(1)
        raw(p, 15) = win(2)
        raw(p, 16) = win(3)
        raw(p, 17) = win(4)
        raw(p, 18) = win(5)
        raw(p, 19) = win(6)
    Next p

    ConnSummaryCore = raw
End Function

'=========================================================
'   PUBLIC WORKSHEET FUNCTION
'=========================================================
Public Function ConnSummary_All_WithNLType_AndScores() As Variant
    Dim MD As String, AD As String, PD As String
    Dim SU As String, PRANA As String, DEH As String

    ' ?? THESE MUST BE CELL REFERENCES PASSED VIA NAMES OR CONSTANTS
    MD = Range("GG20").Value
    AD = Range("GH20").Value
    PD = Range("GI20").Value
    SU = Range("GJ20").Value
    PRANA = Range("GK20").Value
    DEH = Range("GL20").Value

    ConnSummary_All_WithNLType_AndScores = _
        ConnSummaryCore(Empty, MD, AD, PD, SU, PRANA, DEH)
End Function


