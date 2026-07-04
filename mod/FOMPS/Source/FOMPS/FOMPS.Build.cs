using UnrealBuildTool;

public class FOMPS : ModuleRules
{
    public FOMPS(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "FactoryGame" });
        PrivateDependencyModuleNames.AddRange(new string[] { "HTTP", "Json", "UMG", "InputCore", "Slate", "SlateCore" });
    }
}
