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
        ".github/workflows/dotnet-validate.yml",
        ".github/workflows/publish-image.yml",
        ".github/workflows/gitops-handoff.yml",
        "scripts/Set-GitOpsImageDigest.ps1",
        "scripts/Test-LegacyPublication.ps1",
        "scripts/Publish-LegacyRepository.ps1",
    ];

    private static readonly string[] RequiredWorkflows =
    [
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
    public void WorkflowSources_WhenContractIsEvaluated_AreSafeAndShaPinned()
    {
        string repositoryRoot = FindRepositoryRoot();

        foreach (string relativePath in RequiredWorkflows)
        {
            string workflowPath = Path.Combine(repositoryRoot, relativePath);
            Assert.True(File.Exists(workflowPath), $"Missing required workflow: {relativePath}");

            string source = File.ReadAllText(workflowPath);
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

    public static string FindRepositoryRoot()
    {
        DirectoryInfo? currentDirectory = new(AppContext.BaseDirectory);

        while (currentDirectory is not null)
        {
            if (Directory.Exists(Path.Combine(currentDirectory.FullName, ".git")))
            {
                return currentDirectory.FullName;
            }

            currentDirectory = currentDirectory.Parent;
        }

        throw new DirectoryNotFoundException("Could not find the repository root containing .git.");
    }
}
