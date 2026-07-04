#include "FOMPSSubsystem.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Blueprint/UserWidget.h"
#include "Kismet/GameplayStatics.h"
#include "GameFramework/PlayerController.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "UObject/SoftObjectPath.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Text/STextBlock.h"
#include "FGHUD.h"
#include "UI/FGGameUI.h"

DEFINE_LOG_CATEGORY_STATIC(LogFOMPS, Log, All);

static const FString FOMPS_BASE = TEXT("http://127.0.0.1:8770");

// The packaged WBP the player built. GameFeatures plugin "FOMPS" mounts its
// content at /FOMPS/, so the widget class is /FOMPS/WBP_FOMPS.WBP_FOMPS_C.
static const TCHAR* FOMPS_PANEL_CLASS = TEXT("/FOMPS/WBP_FOMPS.WBP_FOMPS_C");

void UFOMPSSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    SyncDownOnStart();   // pull-on-host: get the latest before you play
    // Watch pause state on the CORE ticker: unlike a game timer, it keeps
    // firing while the game is paused, so we can react to the Esc menu.
    TickHandle = FTSTicker::GetCoreTicker().AddTicker(
        FTickerDelegate::CreateUObject(this, &UFOMPSSubsystem::PauseWatchTick), 0.2f);
}

void UFOMPSSubsystem::Deinitialize()
{
    if (TickHandle.IsValid())
    {
        FTSTicker::GetCoreTicker().RemoveTicker(TickHandle);
        TickHandle.Reset();
    }
    HideOverlay();
    Super::Deinitialize();
}

bool UFOMPSSubsystem::PauseWatchTick(float /*DeltaTime*/)
{
    UWorld* W = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
    if (!W || !W->IsGameWorld())
    {
        if (bOverlayShown) HideOverlay();
        return true;   // keep ticking
    }
    // Satisfactory runs its own pause; ask FGGameUI whether the Esc menu is up.
    bool bMenu = false;
    APlayerController* PC = W->GetFirstPlayerController();
    if (PC)
    {
        if (AFGHUD* HUD = Cast<AFGHUD>(PC->GetHUD()))
        {
            if (UFGGameUI* UI = HUD->GetGameUI())
            {
                bMenu = UI->IsPauseMenuOpen();
            }
        }
    }
    if (bMenu != bOverlayShown)
    {
        UE_LOG(LogFOMPS, Warning, TEXT("FOMPS: pause menu %s"), bMenu ? TEXT("OPENED -> showing button") : TEXT("closed -> hiding"));
        if (bMenu) ShowLauncher();
        else       HideOverlay();
    }
    return true;
}

void UFOMPSSubsystem::ShowLauncher()
{
    if (!GEngine || !GEngine->GameViewport) return;
    Launcher =
        SNew(SBox)
        .HAlign(HAlign_Right).VAlign(VAlign_Top)
        .Padding(FMargin(0.f, 28.f, 28.f, 0.f))
        [
            SNew(SButton)
            .ContentPadding(FMargin(20.f, 10.f))
            .OnClicked_Lambda([this]() { TogglePanel(); return FReply::Handled(); })
            [
                SNew(STextBlock).Text(FText::FromString(TEXT("FOMPS")))
            ]
        ];
    GEngine->GameViewport->AddViewportWidgetContent(Launcher.ToSharedRef(), 10000);
    bOverlayShown = true;
    UE_LOG(LogFOMPS, Warning, TEXT("FOMPS: launcher button added to viewport (top-right)"));
}

void UFOMPSSubsystem::HideOverlay()
{
    if (bPanelOpen && Panel)
    {
        Panel->RemoveFromParent();
    }
    Panel = nullptr;
    bPanelOpen = false;
    if (Launcher.IsValid() && GEngine && GEngine->GameViewport)
    {
        GEngine->GameViewport->RemoveViewportWidgetContent(Launcher.ToSharedRef());
    }
    Launcher.Reset();
    bOverlayShown = false;
}

void UFOMPSSubsystem::TogglePanel()
{
    if (bPanelOpen && Panel)          // second click closes it again
    {
        Panel->RemoveFromParent();
        Panel = nullptr;
        bPanelOpen = false;
        return;
    }
    APlayerController* PC = GetGameInstance()
        ? GetGameInstance()->GetFirstLocalPlayerController() : nullptr;
    if (!PC) return;
    if (!Panel)
    {
        UClass* WBP = FSoftClassPath(FOMPS_PANEL_CLASS).TryLoadClass<UUserWidget>();
        if (!WBP)
        {
            UE_LOG(LogFOMPS, Warning, TEXT("FOMPS: panel class not found at %s"), FOMPS_PANEL_CLASS);
            return;
        }
        Panel = CreateWidget<UUserWidget>(PC, WBP);
    }
    if (Panel)
    {
        Panel->AddToViewport(120);   // above the launcher button
        bPanelOpen = true;
    }
}

void UFOMPSSubsystem::SyncDownOnStart()
{
    TWeakObjectPtr<UFOMPSSubsystem> WeakThis(this);
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetVerb(TEXT("POST"));
    Req->SetURL(FOMPS_BASE + TEXT("/api/sync-down"));
    Req->SetHeader(TEXT("User-Agent"), TEXT("FOMPS-Mod/0.1"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->OnProcessRequestComplete().BindLambda(
        [WeakThis](FHttpRequestPtr, FHttpResponsePtr Resp, bool bOk)
        {
            UE_LOG(LogFOMPS, Warning, TEXT("FOMPS sync-down: %s"),
                (bOk && Resp.IsValid()) ? *Resp->GetContentAsString().Left(160)
                                        : TEXT("app not reachable on 127.0.0.1:8770"));
            if (WeakThis.IsValid())
            {
                WeakThis->bAppReachable = bOk && Resp.IsValid();
            }
        });
    Req->ProcessRequest();
}

void UFOMPSSubsystem::RefreshWorlds()
{
    TWeakObjectPtr<UFOMPSSubsystem> WeakThis(this);
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetVerb(TEXT("GET"));
    Req->SetURL(FOMPS_BASE + TEXT("/api/state"));
    Req->SetHeader(TEXT("User-Agent"), TEXT("FOMPS-Mod/0.1"));
    Req->OnProcessRequestComplete().BindLambda(
        [WeakThis](FHttpRequestPtr, FHttpResponsePtr Resp, bool bOk)
        {
            TArray<FFOMPSWorld> Worlds;
            const bool bReachable = bOk && Resp.IsValid();
            if (bReachable)
            {
                TSharedPtr<FJsonObject> Root;
                const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Resp->GetContentAsString());
                if (FJsonSerializer::Deserialize(Reader, Root) && Root.IsValid())
                {
                    const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
                    if (Root->TryGetArrayField(TEXT("worlds"), Arr))
                    {
                        for (const TSharedPtr<FJsonValue>& V : *Arr)
                        {
                            const TSharedPtr<FJsonObject> O = V->AsObject();
                            if (!O.IsValid()) continue;
                            FFOMPSWorld W;
                            W.Ref     = O->GetStringField(TEXT("ref"));
                            W.Code    = O->GetStringField(TEXT("code"));
                            W.Session = O->GetStringField(TEXT("session"));
                            W.Version = static_cast<int32>(O->GetNumberField(TEXT("version")));
                            const TSharedPtr<FJsonObject>* Lock = nullptr;
                            if (O->TryGetObjectField(TEXT("lock"), Lock) && Lock && Lock->IsValid())
                            {
                                W.Host = (*Lock)->GetStringField(TEXT("holder"));
                            }
                            Worlds.Add(W);
                        }
                    }
                }
            }
            if (WeakThis.IsValid())
            {
                WeakThis->bAppReachable = bReachable;
                WeakThis->OnWorlds.Broadcast(Worlds);
            }
        });
    Req->ProcessRequest();
}

void UFOMPSSubsystem::HostWorld(const FString& Ref)   { PostAction(TEXT("/api/host"),   Ref); }
void UFOMPSSubsystem::FinishWorld(const FString& Ref) { PostAction(TEXT("/api/finish"), Ref); }

void UFOMPSSubsystem::PostAction(const FString& Path, const FString& Ref)
{
    TWeakObjectPtr<UFOMPSSubsystem> WeakThis(this);
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetVerb(TEXT("POST"));
    Req->SetURL(FOMPS_BASE + Path);
    Req->SetHeader(TEXT("User-Agent"), TEXT("FOMPS-Mod/0.1"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(FString::Printf(TEXT("{\"ref\":\"%s\"}"), *Ref));
    Req->OnProcessRequestComplete().BindLambda(
        [WeakThis](FHttpRequestPtr, FHttpResponsePtr Resp, bool bOk)
        {
            const bool bSuccess = bOk && Resp.IsValid()
                && Resp->GetResponseCode() >= 200 && Resp->GetResponseCode() < 300;
            const FString Msg = (bOk && Resp.IsValid())
                ? Resp->GetContentAsString().Left(160)
                : TEXT("app not reachable on 127.0.0.1:8770");
            UE_LOG(LogFOMPS, Warning, TEXT("FOMPS action: %s"), *Msg);
            if (WeakThis.IsValid())
            {
                WeakThis->OnActionResult.Broadcast(bSuccess, Msg);
                WeakThis->RefreshWorlds();
            }
        });
    Req->ProcessRequest();
}
