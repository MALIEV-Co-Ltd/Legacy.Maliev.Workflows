using System.Text.RegularExpressions;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class RepositoryContractTests
{
    private static readonly string[] RequiredFiles =
    [
        "README.md",
        "SECURITY.md",
        ".github/dependabot.yml",
        "actions/dotnet-validate/action.yml",
        ".github/workflows/dotnet-validate.yml",
        ".github/workflows/publish-image.yml",
        ".github/workflows/gitops-handoff.yml",
        "scripts/Set-GitOpsImageDigest.ps1",
        "scripts/Test-LegacyPublication.ps1",
        "scripts/Publish-LegacyRepository.ps1",
    ];

    private static readonly string[] RequiredActionSources =
    [
        "actions/dotnet-validate/action.yml",
        ".github/workflows/dotnet-validate.yml",
        ".github/workflows/publish-image.yml",
        ".github/workflows/gitops-handoff.yml",
    ];

    [Fact]
    public void RequiredRepositoryFiles_WhenContractIsEvaluated_AllExist()
    {
        string repositoryRoot = FindRepositoryRoot();
        string[] missingFiles = RequiredFiles
            .Where(relativePath => !File.Exists(Path.Combine(repositoryRoot, relativePath)))
            .ToArray();

        Assert.True(
            missingFiles.Length == 0,
            $"Missing required repository files:{Environment.NewLine}{string.Join(Environment.NewLine, missingFiles)}");
    }

    [Fact]
    public void ActionSources_WhenContractIsEvaluated_AreSafeAndShaPinned()
    {
        string repositoryRoot = FindRepositoryRoot();

        foreach (string relativePath in RequiredActionSources)
        {
            string sourcePath = Path.Combine(repositoryRoot, relativePath);
            Assert.True(File.Exists(sourcePath), $"Missing required action source: {relativePath}");

            string source = File.ReadAllText(sourcePath);
            Assert.DoesNotContain("pull_request_target", source, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("kubectl", source, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("argocd", source, StringComparison.OrdinalIgnoreCase);

            string[] actionLines = source
                .Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
                .Where(line => Regex.IsMatch(line, @"^\s*(?:-\s*)?uses:\s*", RegexOptions.IgnoreCase))
                .ToArray();

            foreach (string actionLine in actionLines)
            {
                Assert.Matches(@"uses:\s+[^\s@]+@[0-9a-f]{40}(?:\s|$)", actionLine);
            }
        }
    }

    [Fact]
    public void FindRepositoryRoot_WhenGitMarkerIsFileOrDirectory_ReturnsRepositoryRoot()
    {
        DirectoryInfo? expectedRoot = new(AppContext.BaseDirectory);

        while (expectedRoot is not null)
        {
            string gitMarker = Path.Combine(expectedRoot.FullName, ".git");
            if (Directory.Exists(gitMarker) || File.Exists(gitMarker))
            {
                break;
            }

            expectedRoot = expectedRoot.Parent;
        }

        Assert.NotNull(expectedRoot);
        Assert.Equal(expectedRoot.FullName, FindRepositoryRoot());
    }

    public static string FindRepositoryRoot()
    {
        DirectoryInfo? currentDirectory = new(AppContext.BaseDirectory);

        while (currentDirectory is not null)
        {
            string gitMarker = Path.Combine(currentDirectory.FullName, ".git");
            if (Directory.Exists(gitMarker) || File.Exists(gitMarker))
            {
                return currentDirectory.FullName;
            }

            currentDirectory = currentDirectory.Parent;
        }

        throw new DirectoryNotFoundException("Could not find the repository root containing .git.");
    }
}
