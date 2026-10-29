PROGRAM FlyingShearDemo
VAR
    Enable, Prepare, Execute, StopCommand : BOOL;
    Ready, Prepared, Preparing, Running, Coupled, Stopped : BOOL;
    SyncWindow, Synchronized, CutInProgress, CutComplete : BOOL;
    Error : BOOL;
    ErrorID : UDINT;
    PreparePrevious, ExecutePrevious : BOOL;
    PrepareCount, CommandCount, CutCount, CycleIndex : UDINT;
    CutState : DINT;
    FeedActual, CarriageActual, KnifeActual : LREAL;
    FeedVelocity, CarriageVelocity, KnifeVelocity : LREAL;
    Phase, SyncError, SyncVelocityError : LREAL;
    CarriageExpected, KnifeExpected : LREAL;
    MaxCarriageError, MaxKnifeError, MaxSyncError, MaxSyncVelocityError : LREAL;
    LastCutPosition, LastCutDepth, LastCutSyncError, LastCutVelocityError : LREAL;
    LastCutFeed, LastCutCarriage, LastCutKnife : LREAL;
    LastCutCycle, CheckedScans, SyncScans : UDINT;
    Init, Active, RunLatch, ProcessFault, NativeError, StopRequest : BOOL;
    PrepareTrigger, StartTrigger, BottomSeen, Counted : BOOL;
    PreviousCycle : UDINT;
    CutDepth, CutSyncError, CutVelocityError : LREAL;
    Index : INT;
    X, T, CartY, KnifeY : LREAL;
    CartCam : MC_CAM_REF := (byType:=2, byVarType:=2, nElements:=128, xStart:=0.0, xEnd:=160.0, strCAMName:='C6_Carriage');
    KnifeCam : MC_CAM_REF := (byType:=2, byVarType:=2, nElements:=128, xStart:=0.0, xEnd:=160.0, strCAMName:='C6_Knife');
    CartPoints : SMC_CAMTable_UINT_128_2 := (
        fEditorMasterMin:=0, fEditorMasterMax:=160, fTableMasterMin:=0, fTableMasterMax:=6000,
        fEditorSlaveMin:=0, fEditorSlaveMax:=90, fTableSlaveMin:=0, fTableSlaveMax:=6000);
    KnifePoints : SMC_CAMTable_UINT_128_2 := (
        fEditorMasterMin:=0, fEditorMasterMax:=160, fTableMasterMin:=0, fTableMasterMax:=6000,
        fEditorSlaveMin:=0, fEditorSlaveMax:=8, fTableSlaveMin:=0, fTableSlaveMax:=6000);
    FeedPower, CartPower, KnifePower : MC_Power;
    FeedHome, CartHome, KnifeHome : MC_MoveAbsolute;
    FeedRun : MC_MoveVelocity;
    FeedStop, CartStop, KnifeStop : MC_Stop;
    SelectCart, SelectKnife : MC_CamTableSelect;
    CartIn, KnifeIn : MC_CamIn;
END_VAR
