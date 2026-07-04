#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Containers/Ticker.h"
#include "FOMPSSubsystem.generated.h"

class UUserWidget;
class APlayerController;
class SWidget;

/** One shared world as the desktop app reports it. */
USTRUCT(BlueprintType)
struct FFOMPSWorld
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "FOMPS") FString Ref;
    UPROPERTY(BlueprintReadOnly, Category = "FOMPS") FString Code;
    UPROPERTY(BlueprintReadOnly, Category = "FOMPS") FString Session;
    UPROPERTY(BlueprintReadOnly, Category = "FOMPS") int32   Version = 0;
    /** Lock holder's name, or empty if the world is free to host. */
    UPROPERTY(BlueprintReadOnly, Category = "FOMPS") FString Host;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FFOMPSWorldsDelegate, const TArray<FFOMPSWorld>&, Worlds);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FFOMPSResultDelegate, bool, bSuccess, const FString&, Message);

/**
 * In-game bridge to the FOMPS desktop app (127.0.0.1:8770).
 * The UMG panel calls these functions and binds to the delegates.
 */
UCLASS()
class FOMPS_API UFOMPSSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    /** Fetch the world list from the app; result arrives via OnWorlds. */
    UFUNCTION(BlueprintCallable, Category = "FOMPS")
    void RefreshWorlds();

    /** Pull the latest save + claim the host lock, then refresh. */
    UFUNCTION(BlueprintCallable, Category = "FOMPS")
    void HostWorld(const FString& Ref);

    /** Upload your save + release the lock, then refresh. */
    UFUNCTION(BlueprintCallable, Category = "FOMPS")
    void FinishWorld(const FString& Ref);

    /** True if the desktop app answered the last request. */
    UPROPERTY(BlueprintReadOnly, Category = "FOMPS")
    bool bAppReachable = false;

    /** Fires with the current worlds after RefreshWorlds()/an action. */
    UPROPERTY(BlueprintAssignable, Category = "FOMPS")
    FFOMPSWorldsDelegate OnWorlds;

    /** Fires after Host/Finish with success + a message. */
    UPROPERTY(BlueprintAssignable, Category = "FOMPS")
    FFOMPSResultDelegate OnActionResult;

private:
    void SyncDownOnStart();
    void PostAction(const FString& Path, const FString& Ref);

    // --- pause-menu overlay: a "FOMPS" button that shows while the game is
    //     paused; clicking it opens the WBP_FOMPS panel. ---
    /** Runs on the core ticker (fires even while the game is paused). */
    bool PauseWatchTick(float DeltaTime);
    void ShowLauncher();
    void HideOverlay();
    void TogglePanel();

    UPROPERTY() TObjectPtr<UUserWidget> Panel;
    bool bOverlayShown = false;
    bool bPanelOpen = false;
    FTSTicker::FDelegateHandle TickHandle;
    TSharedPtr<SWidget> Launcher;
};
