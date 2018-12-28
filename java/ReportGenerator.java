/**
 * Copyright 2016 Tencent Inc.
 * All rights reserved.
 * 
 * @author wentingli <wentingli@tencent.com>
 *
 * Make a few changes and adjust the input arguments
 * based on jacoco example.
 *
 */

package com.tencent.gdt.blade;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import org.jacoco.core.analysis.Analyzer;
import org.jacoco.core.analysis.CoverageBuilder;
import org.jacoco.core.analysis.IBundleCoverage;
import org.jacoco.core.tools.ExecFileLoader;
import org.jacoco.report.DirectorySourceFileLocator;
import org.jacoco.report.FileMultiReportOutput;
import org.jacoco.report.IReportVisitor;
import org.jacoco.report.ISourceFileLocator;
import org.jacoco.report.MultiSourceFileLocator;
import org.jacoco.report.html.HTMLFormatter;
import org.jacoco.report.xml.XMLFormatter;

/**
 * The ReportGenerator class creates a HTML report based on classes files
 * and execution data called jacoco.exec collected by jacoco agent.
 * 
 * The class files under test must be compiled with debug information, otherwise
 * source highlighting will not work.
 */
public class ReportGenerator {

  private static final String TITLE = "Java Coverage Report";
  private static final int TAB_WIDTH = 2;

  private final File reportDirectory;
  private Set<String> sourceDirectories;
  private List<File> classDirectories;
  private List<File> executionDataFiles;

  private ExecFileLoader execFileLoader;
  private MultiSourceFileLocator sourceFileLocator;

  /**
   * Create a report generator.
   * 
   * @param reportDirectory
   *      directory to put coverage reports
   */
  public ReportGenerator(String reportDirectory) {
    this.reportDirectory = new File(reportDirectory);
    this.sourceDirectories = new HashSet<String>();
    this.classDirectories = new ArrayList<File>();
    this.executionDataFiles = new ArrayList<File>();
    this.execFileLoader = new ExecFileLoader();
    this.sourceFileLocator = new MultiSourceFileLocator(TAB_WIDTH);
  }

  /**
   * Add project information used to generate report.
   *
   * @param sourceDirectory
   *      the root of source directory where all source
   *      files are located according to the package structure
   *
   * @param classDirectory
   *      class directory with package structure containing
   *      classes to be analyzed
   *
   * @param executionData
   *      execution data file(jacoco.exec) collected by jacoco agent
   *
   */
  public void addProjectInfo(String sourceDirectory,
                             String classDirectory,
                             String executionData) {
    sourceDirectories.add(sourceDirectory);
    classDirectories.add(new File(classDirectory));
    executionDataFiles.add(new File(executionData));
  }

  /**
   * Create the report.
   * 
   * @throws IOException
   */
  public void createReport() throws IOException {
    loadExecutionData();
    IBundleCoverage bundleCoverage = analyzeStructure();
    generateReport(bundleCoverage);
  }

  private void generateReport(IBundleCoverage bundleCoverage)
          throws IOException {
    HTMLFormatter htmlFormatter = new HTMLFormatter();
    IReportVisitor visitor = htmlFormatter.createVisitor(
        new FileMultiReportOutput(reportDirectory));
    generateReport(bundleCoverage, visitor);
    final String xmlReport = System.getenv("JACOCO_XML_REPORT");
    if (xmlReport != null) {
      XMLFormatter xmlFormatter = new XMLFormatter();
      visitor = xmlFormatter.createVisitor(new FileOutputStream(
          reportDirectory.getPath() + "/jacoco_coverage_report.xml"));
      generateReport(bundleCoverage, visitor);
    }
  }

  private void generateReport(IBundleCoverage bundleCoverage,
                              IReportVisitor visitor) throws IOException {
    visitor.visitInfo(execFileLoader.getSessionInfoStore().getInfos(),
                      execFileLoader.getExecutionDataStore().getContents());

    for (String sourceDirectory : sourceDirectories) {
      sourceFileLocator.add(new DirectorySourceFileLocator(
          new File(sourceDirectory), "utf-8", TAB_WIDTH));
    }
    visitor.visitBundle(bundleCoverage, sourceFileLocator);

    visitor.visitEnd();
  }

  private void loadExecutionData() throws IOException {
    for (File executionDataFile : executionDataFiles) {
      execFileLoader.load(executionDataFile);
    }
  }

  private IBundleCoverage analyzeStructure() throws IOException {
    CoverageBuilder coverageBuilder = new CoverageBuilder();
    Analyzer analyzer = new Analyzer(
        execFileLoader.getExecutionDataStore(), coverageBuilder);

    for (File classDirectory : classDirectories) {
      analyzer.analyzeAll(classDirectory);
    }
    return coverageBuilder.getBundle(TITLE);
  }

  /**
   * Starts the coverage report generation
   * 
   * @param args Arguments to the application.
   *      The first argument is the report directory.
   *      The rest of arguments are (source directory, class
   *      directory, execution data) pairs for each project
   *      for which ReportGenerator will generate coverage report.
   * @throws IOException
   */
  public static void main(String[] args) throws IOException {
    ReportGenerator generator = new ReportGenerator(args[0]);
    for (int i = 1; i < args.length; i++) {
      String[] parts = args[i].split(",");
      generator.addProjectInfo(parts[0], parts[1], parts[2]);
    }
    generator.createReport();
  }
}
