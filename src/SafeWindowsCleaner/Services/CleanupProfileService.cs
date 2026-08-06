using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class CleanupProfileService
{
    public const string SafeProfile = "safe";
    public const string BrowserProfile = "browser";
    public const string SpaceProfile = "space";
    public const string ReviewProfile = "review";

    public IReadOnlyList<CleanupProfileOption> GetProfiles(string languageCode)
    {
        return
        [
            new CleanupProfileOption
            {
                Id = SafeProfile,
                Name = LocalizationService.T("@ProfileSafe", languageCode),
                Description = LocalizationService.T("@ProfileSafeDescription", languageCode)
            },
            new CleanupProfileOption
            {
                Id = BrowserProfile,
                Name = LocalizationService.T("@ProfileBrowser", languageCode),
                Description = LocalizationService.T("@ProfileBrowserDescription", languageCode)
            },
            new CleanupProfileOption
            {
                Id = SpaceProfile,
                Name = LocalizationService.T("@ProfileSpace", languageCode),
                Description = LocalizationService.T("@ProfileSpaceDescription", languageCode)
            },
            new CleanupProfileOption
            {
                Id = ReviewProfile,
                Name = LocalizationService.T("@ProfileReview", languageCode),
                Description = LocalizationService.T("@ProfileReviewDescription", languageCode)
            }
        ];
    }

    public void Apply(string? profileId, IEnumerable<CleanupTarget> targets)
    {
        string profile = Normalize(profileId);
        foreach (CleanupTarget target in targets)
        {
            target.IsSelected = profile switch
            {
                BrowserProfile => target.SafetyTier == CleanupSafetyTier.Safe
                                  && string.Equals(target.Group, "Browser", StringComparison.OrdinalIgnoreCase),
                SpaceProfile => target.SafetyTier == CleanupSafetyTier.Safe
                                && target.MinimumAge >= TimeSpan.FromHours(6),
                ReviewProfile => target.SafetyTier is CleanupSafetyTier.Safe or CleanupSafetyTier.Review,
                _ => target.SafetyTier == CleanupSafetyTier.Safe && target.EnabledByDefault
            };
        }
    }

    public static string Normalize(string? profileId)
    {
        string value = (profileId ?? string.Empty).Trim().ToLowerInvariant();
        return value is BrowserProfile or SpaceProfile or ReviewProfile ? value : SafeProfile;
    }

    public static string NormalizeForAutomatic(string? profileId)
    {
        string normalized = Normalize(profileId);
        return normalized == ReviewProfile ? SafeProfile : normalized;
    }
}
