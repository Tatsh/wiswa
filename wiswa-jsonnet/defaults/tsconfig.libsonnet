/**
 * @file tsconfig.libsonnet
 * @brief Default configuration for TypeScript projects.
 * @namespace tsconfig
 * @sa [TSConfig Reference](https://www.typescriptlang.org/tsconfig/)
 */
{
  /** @brief TypeScript compiler options. */
  compilerOptions: {
    /** @brief Allow JavaScript files to be compiled. */
    allowJs: true,
    /** @brief Enable all strict type-checking options. */
    alwaysStrict: true,
    /** @brief Disable loading of referenced projects. */
    disableReferencedProjectLoad: true,
    /** @brief Disable searching for solutions. */
    disableSolutionSearching: true,
    /** @brief Enable interoperability between CommonJS and ES Modules. */
    esModuleInterop: true,
    /** @brief Enable experimental support for decorators. */
    experimentalDecorators: true,
    /** @brief Ensure consistent casing in file names. */
    forceConsistentCasingInFileNames: true,
    /** @brief Compile each file as a separate module. */
    isolatedModules: true,
    /** @brief List of library files to be included in the compilation. */
    lib: ['dom', 'dom.iterable', 'esnext'],
    /** @brief Module code generation method. */
    module: 'commonjs',
    /** @brief Module resolution strategy. */
    moduleResolution: 'bundler',
    /** @brief Disable truncation of error messages. */
    noErrorTruncation: true,
    /** @brief Report errors for fallthrough cases in switch statements. */
    noFallthroughCasesInSwitch: true,
    /** @brief Raise error on expressions and declarations with an implied "any" type. */
    noImplicitAny: true,
    /** @brief Report error when not all code paths in function return a value. */
    noImplicitReturns: true,
    /** @brief Raise error on "this" expressions with an implied "any" type. */
    noImplicitThis: true,
    /** @brief Directory to output compiled JavaScript files. */
    outDir: './dist/',
    /** @brief Do not erase const enum declarations in generated code. */
    preserveConstEnums: true,
    /** @brief Enable pretty output. */
    pretty: true,
    /** @brief Enable importing .json files as modules. */
    resolveJsonModule: true,
    /** @brief Skip type checking of declaration files. */
    skipLibCheck: true,
    /** @brief Generate corresponding .map files for debugging. */
    sourceMap: true,
    /** @brief Enable all strict type-checking options. */
    strict: true,
    /** @brief Remove declarations marked as @internal in the generated .d.ts files. */
    stripInternal: true,
    /** @brief Specify ECMAScript target version. */
    target: 'es6',
  },
  /** @brief List of files or directories to include in the compilation. */
  include: ['src'],
}
