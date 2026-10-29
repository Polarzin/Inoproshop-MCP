(* 原创合成飞剪；两张原生凸轮共用送料轴，三轴均为 SM_Drive_Virtual。 *)
IF NOT Init THEN
    FOR Index := 0 TO 127 DO
        X := INT_TO_LREAL(Index) / 127.0 * 160.0;
        IF X < 30.0 THEN
            T := X / 30.0;
            CartY := 30.0*T*T*T*T*(2.5 + T*(-3.0 + T));
        ELSIF X <= 90.0 THEN
            CartY := X - 15.0;
        ELSIF X < 120.0 THEN
            T := (X-90.0)/30.0;
            CartY := 75.0 + 30.0*(T - T*T*T*T*(2.5 + T*(-3.0 + T)));
        ELSE
            T := (X-120.0)/40.0;
            CartY := 90.0*(1.0-T*T*T*(10.0+T*(-15.0+6.0*T)));
        END_IF;
        KnifeY := 0.0;
        IF X >= 42.0 AND X < 58.0 THEN
            T := (X-42.0)/16.0;
            KnifeY := 8.0*T*T*T*(10.0+T*(-15.0+6.0*T));
        ELSIF X >= 58.0 AND X <= 62.0 THEN
            KnifeY := 8.0;
        ELSIF X > 62.0 AND X < 78.0 THEN
            T := (X-62.0)/16.0;
            KnifeY := 8.0*(1.0-T*T*T*(10.0+T*(-15.0+6.0*T)));
        END_IF;
        CartPoints.Table[Index][0] := LREAL_TO_UINT(X/160.0*6000.0);
        CartPoints.Table[Index][1] := LREAL_TO_UINT(CartY/90.0*6000.0);
        KnifePoints.Table[Index][0] := CartPoints.Table[Index][0];
        KnifePoints.Table[Index][1] := LREAL_TO_UINT(KnifeY/8.0*6000.0);
    END_FOR;
    Init := TRUE;
END_IF;
CartCam.pce := ADR(CartPoints);
KnifeCam.pce := ADR(KnifePoints);
FeedPower(Axis:=Feed, Enable:=TRUE, bRegulatorOn:=Enable, bDriveStart:=Enable);
CartPower(Axis:=Carriage, Enable:=TRUE, bRegulatorOn:=Enable, bDriveStart:=Enable);
KnifePower(Axis:=Knife, Enable:=TRUE, bRegulatorOn:=Enable, bDriveStart:=Enable);
Ready := FeedPower.Status AND CartPower.Status AND KnifePower.Status;
SelectCart(Master:=Feed, Slave:=Carriage, CamTable:=CartCam, Execute:=Ready,
    Periodic:=TRUE, MasterAbsolute:=TRUE, SlaveAbsolute:=TRUE);
SelectKnife(Master:=Feed, Slave:=Knife, CamTable:=KnifeCam, Execute:=Ready,
    Periodic:=TRUE, MasterAbsolute:=TRUE, SlaveAbsolute:=TRUE);
PrepareTrigger := Prepare AND NOT PreparePrevious AND Ready AND NOT StopCommand
    AND NOT Active AND NOT Preparing AND NOT Error;
StartTrigger := Execute AND NOT ExecutePrevious AND Prepared AND Ready
    AND SelectCart.Done AND SelectKnife.Done AND NOT StopCommand AND NOT Error;
PreparePrevious := Prepare;
ExecutePrevious := Execute;
IF PrepareTrigger THEN
    Preparing := TRUE;
    Prepared := FALSE;
    PrepareCount := PrepareCount + 1;
END_IF;
IF StartTrigger THEN
    Active := TRUE;
    RunLatch := FALSE;
    Prepared := FALSE;
    CommandCount := CommandCount + 1;
    CutCount := 0;
    CycleIndex := 0;
    PreviousCycle := 0;
    BottomSeen := FALSE;
    Counted := FALSE;
    CutDepth := 0.0;
    CutSyncError := 0.0;
    CutVelocityError := 0.0;
    CheckedScans := 0;
    SyncScans := 0;
    MaxCarriageError := 0.0;
    MaxKnifeError := 0.0;
    MaxSyncError := 0.0;
    MaxSyncVelocityError := 0.0;
END_IF;
StopRequest := StopCommand OR ProcessFault OR NativeError;
IF StopRequest OR NOT Enable THEN
    Active := FALSE;
    RunLatch := FALSE;
    Preparing := FALSE;
    Prepared := FALSE;
    BottomSeen := FALSE;
END_IF;
FeedHome(Axis:=Feed, Execute:=Preparing, Position:=0.0, Velocity:=90.0,
    Acceleration:=120.0, Deceleration:=120.0, Jerk:=0.0);
CartHome(Axis:=Carriage, Execute:=Preparing, Position:=0.0, Velocity:=40.0,
    Acceleration:=100.0, Deceleration:=100.0, Jerk:=0.0);
KnifeHome(Axis:=Knife, Execute:=Preparing, Position:=0.0, Velocity:=15.0,
    Acceleration:=100.0, Deceleration:=100.0, Jerk:=0.0);
IF Preparing AND FeedHome.Done AND CartHome.Done AND KnifeHome.Done THEN
    Preparing := FALSE;
    Prepared := TRUE;
END_IF;
IF Active AND CartIn.InSync AND KnifeIn.InSync THEN RunLatch := TRUE; END_IF;
FeedRun(Axis:=Feed, Execute:=RunLatch, Velocity:=20.0,
    Acceleration:=50.0, Deceleration:=50.0, Jerk:=0.0, Direction:=MC_Direction.positive);
CartIn(Master:=Feed, Slave:=Carriage, Execute:=Active, CamTableID:=SelectCart.CamTableID,
    MasterOffset:=0.0, SlaveOffset:=0.0, MasterScaling:=1.0, SlaveScaling:=1.0,
    StartMode:=MC_StartMode.absolute, VelocityDiff:=20.0, Acceleration:=100.0, Deceleration:=100.0, Jerk:=0.0);
KnifeIn(Master:=Feed, Slave:=Knife, Execute:=Active, CamTableID:=SelectKnife.CamTableID,
    MasterOffset:=0.0, SlaveOffset:=0.0, MasterScaling:=1.0, SlaveScaling:=1.0,
    StartMode:=MC_StartMode.absolute, VelocityDiff:=20.0, Acceleration:=100.0, Deceleration:=100.0, Jerk:=0.0);
FeedStop(Axis:=Feed, Execute:=StopRequest AND FeedPower.Status, Deceleration:=50.0, Jerk:=0.0);
CartStop(Axis:=Carriage, Execute:=StopRequest AND CartPower.Status, Deceleration:=100.0, Jerk:=0.0);
KnifeStop(Axis:=Knife, Execute:=StopRequest AND KnifePower.Status, Deceleration:=100.0, Jerk:=0.0);
Coupled := CartIn.InSync AND KnifeIn.InSync;
Running := Active AND RunLatch AND Coupled;
Stopped := FeedStop.Done AND CartStop.Done AND KnifeStop.Done;
FeedActual := Feed.fActPosition;
CarriageActual := Carriage.fActPosition;
KnifeActual := Knife.fActPosition;
FeedVelocity := Feed.fActVelocity;
CarriageVelocity := Carriage.fActVelocity;
KnifeVelocity := Knife.fActVelocity;
CycleIndex := DINT_TO_UDINT(MAX(0, TRUNC(FeedActual/160.0)));
Phase := FeedActual - UDINT_TO_LREAL(CycleIndex)*160.0;
X := Phase;
IF X < 30.0 THEN
    T := X/30.0;
    CarriageExpected := 30.0*T*T*T*T*(2.5+T*(-3.0+T));
ELSIF X <= 90.0 THEN
    CarriageExpected := X-15.0;
ELSIF X < 120.0 THEN
    T := (X-90.0)/30.0;
    CarriageExpected := 75.0+30.0*(T-T*T*T*T*(2.5+T*(-3.0+T)));
ELSE
    T := (X-120.0)/40.0;
    CarriageExpected := 90.0*(1.0-T*T*T*(10.0+T*(-15.0+6.0*T)));
END_IF;
KnifeExpected := 0.0;
IF X >= 42.0 AND X < 58.0 THEN
    T := (X-42.0)/16.0;
    KnifeExpected := 8.0*T*T*T*(10.0+T*(-15.0+6.0*T));
ELSIF X >= 58.0 AND X <= 62.0 THEN
    KnifeExpected := 8.0;
ELSIF X > 62.0 AND X < 78.0 THEN
    T := (X-62.0)/16.0;
    KnifeExpected := 8.0*(1.0-T*T*T*(10.0+T*(-15.0+6.0*T)));
END_IF;
SyncWindow := Running AND Phase >= 30.0 AND Phase <= 90.0;
SyncError := CarriageActual - (Phase-15.0);
SyncVelocityError := CarriageVelocity - FeedVelocity;
Synchronized := SyncWindow AND ABS(SyncError) <= 0.35 AND ABS(SyncVelocityError) <= 0.75
    AND ABS(FeedVelocity-20.0) <= 0.01;
CutInProgress := Running AND KnifeActual > 0.1;
CutState := 0;
IF Running THEN
    CheckedScans := CheckedScans + 1;
    MaxCarriageError := MAX(MaxCarriageError, ABS(CarriageActual-CarriageExpected));
    MaxKnifeError := MAX(MaxKnifeError, ABS(KnifeActual-KnifeExpected));
    IF CycleIndex <> PreviousCycle THEN
        BottomSeen := FALSE;
        Counted := FALSE;
        CutDepth := 0.0;
        CutSyncError := 0.0;
        CutVelocityError := 0.0;
        PreviousCycle := CycleIndex;
    END_IF;
    CutState := 1;
    IF SyncWindow THEN CutState := 2; END_IF;
    IF Phase > 90.0 THEN CutState := 6; END_IF;
    IF CutInProgress THEN
        CutState := 3;
        IF KnifeActual >= 7.9 THEN CutState := 4; END_IF;
        IF KnifeVelocity < -0.001 THEN CutState := 5; END_IF;
        CutDepth := MAX(CutDepth, KnifeActual);
        CutSyncError := MAX(CutSyncError, ABS(SyncError));
        CutVelocityError := MAX(CutVelocityError, ABS(SyncVelocityError));
        IF NOT Synchronized THEN ProcessFault := TRUE; END_IF;
        IF KnifeActual >= 7.9 AND Synchronized THEN BottomSeen := TRUE; END_IF;
    END_IF;
    IF SyncWindow THEN
        SyncScans := SyncScans + 1;
        MaxSyncError := MAX(MaxSyncError, ABS(SyncError));
        MaxSyncVelocityError := MAX(MaxSyncVelocityError, ABS(SyncVelocityError));
    END_IF;
    IF BottomSeen AND NOT Counted AND NOT ProcessFault AND Synchronized
        AND Phase > 70.0 AND KnifeActual <= 0.1 THEN
        CutCount := CutCount + 1;
        Counted := TRUE;
        LastCutPosition := FeedActual-CarriageActual;
        LastCutDepth := CutDepth;
        LastCutSyncError := CutSyncError;
        LastCutVelocityError := CutVelocityError;
        LastCutFeed := FeedActual;
        LastCutCarriage := CarriageActual;
        LastCutKnife := KnifeActual;
        LastCutCycle := CycleIndex;
    END_IF;
END_IF;
CutComplete := Running AND Counted;
NativeError := FeedPower.Error OR CartPower.Error OR KnifePower.Error OR SelectCart.Error OR SelectKnife.Error
    OR FeedHome.Error OR CartHome.Error OR KnifeHome.Error OR FeedRun.Error OR CartIn.Error OR KnifeIn.Error
    OR FeedStop.Error OR CartStop.Error OR KnifeStop.Error;
Error := NativeError OR ProcessFault;
ErrorID := 0;
IF ProcessFault THEN ErrorID := 60001; END_IF;
IF FeedPower.Error THEN ErrorID := TO_UDINT(FeedPower.ErrorID); END_IF;
IF CartPower.Error THEN ErrorID := TO_UDINT(CartPower.ErrorID); END_IF;
IF KnifePower.Error THEN ErrorID := TO_UDINT(KnifePower.ErrorID); END_IF;
IF SelectCart.Error THEN ErrorID := TO_UDINT(SelectCart.ErrorID); END_IF;
IF SelectKnife.Error THEN ErrorID := TO_UDINT(SelectKnife.ErrorID); END_IF;
IF FeedHome.Error THEN ErrorID := TO_UDINT(FeedHome.ErrorID); END_IF;
IF CartHome.Error THEN ErrorID := TO_UDINT(CartHome.ErrorID); END_IF;
IF KnifeHome.Error THEN ErrorID := TO_UDINT(KnifeHome.ErrorID); END_IF;
IF FeedRun.Error THEN ErrorID := TO_UDINT(FeedRun.ErrorID); END_IF;
IF CartIn.Error THEN ErrorID := TO_UDINT(CartIn.ErrorID); END_IF;
IF KnifeIn.Error THEN ErrorID := TO_UDINT(KnifeIn.ErrorID); END_IF;
IF FeedStop.Error THEN ErrorID := TO_UDINT(FeedStop.ErrorID); END_IF;
IF CartStop.Error THEN ErrorID := TO_UDINT(CartStop.ErrorID); END_IF;
IF KnifeStop.Error THEN ErrorID := TO_UDINT(KnifeStop.ErrorID); END_IF;
